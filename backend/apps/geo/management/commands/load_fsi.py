"""
load_fsi — sample FSI input rasters into HexCell rows and compute fsi_score.

Expected raster filenames (any extension: .tif, .tiff, .img):
    twi, hand, slope, imperviousness, depression_depth, dist_to_water

Usage:
    manage.py load_fsi --layers /path/to/rasters/

All rasters must share the same CRS (preferably EPSG:4326 or any projected CRS;
pyproj will reproject centroid coordinates as needed).

FSI score uses equal weights (1/6 each) by default.  Override with --weights.
"""
import logging
import os
from pathlib import Path

import numpy as np
from django.core.management.base import BaseCommand, CommandError

from apps.geo.models import HexCell

logger = logging.getLogger(__name__)

LAYER_NAMES = ["twi", "hand", "slope", "imperviousness", "depression_depth", "dist_to_water"]
LAYER_ALIASES = {
    "dep": "depression_depth",
    "depression": "depression_depth",
    "dist_water": "dist_to_water",
    "distance_to_water": "dist_to_water",
    "impervious": "imperviousness",
}
RASTER_EXTS = {".tif", ".tiff", ".img", ".vrt"}


def _find_rasters(layer_dir: Path) -> dict[str, Path]:
    """Map layer name → raster path by fuzzy-matching filenames."""
    found: dict[str, Path] = {}
    for f in layer_dir.iterdir():
        if f.suffix.lower() not in RASTER_EXTS:
            continue
        stem = f.stem.lower()
        # direct match
        if stem in LAYER_NAMES:
            found[stem] = f
            continue
        # alias match
        if stem in LAYER_ALIASES:
            found[LAYER_ALIASES[stem]] = f
            continue
        # prefix match (e.g. twi_hyderabad.tif → twi)
        for name in LAYER_NAMES:
            if stem.startswith(name):
                found[name] = f
                break
    return found


def _sample_raster(raster_path: Path, coords_wgs84: list[tuple[float, float]]) -> np.ndarray:
    """
    Sample raster at WGS-84 (lng, lat) point list.
    Returns float array of length len(coords_wgs84); NaN where nodata.
    """
    try:
        import rasterio
        from rasterio.crs import CRS
        from pyproj import Transformer
    except ImportError as exc:
        raise CommandError(f"rasterio/pyproj not installed: {exc}") from exc

    with rasterio.open(raster_path) as src:
        raster_crs = src.crs
        wgs84 = CRS.from_epsg(4326)
        if raster_crs != wgs84:
            transformer = Transformer.from_crs(wgs84, raster_crs, always_xy=True)
            xs = [c[0] for c in coords_wgs84]
            ys = [c[1] for c in coords_wgs84]
            xs_proj, ys_proj = transformer.transform(xs, ys)
            proj_coords = list(zip(xs_proj, ys_proj))
        else:
            proj_coords = coords_wgs84

        nodata = src.nodata
        values = []
        for val in src.sample(proj_coords, indexes=1):
            v = float(val[0])
            if nodata is not None and v == nodata:
                v = float("nan")
            values.append(v)

    return np.array(values, dtype=float)


def _normalize(arr: np.ndarray) -> np.ndarray:
    """Min-max normalize to [0, 1]; NaN passes through as 0."""
    valid = arr[~np.isnan(arr)]
    if len(valid) == 0 or valid.max() == valid.min():
        return np.where(np.isnan(arr), 0.0, 0.5)
    mn, mx = valid.min(), valid.max()
    result = (arr - mn) / (mx - mn)
    return np.where(np.isnan(result), 0.0, result)


class Command(BaseCommand):
    help = "Sample FSI input rasters into HexCell.fsi_inputs and compute fsi_score."

    def add_arguments(self, parser):
        parser.add_argument(
            "--layers",
            required=True,
            help="Directory containing raster files for FSI inputs.",
        )
        parser.add_argument(
            "--weights",
            nargs=6,
            type=float,
            metavar=tuple(LAYER_NAMES),
            default=None,
            help="Weights for each FSI layer (must sum to 1.0). Default: equal (1/6 each).",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            dest="batch_size",
        )
        parser.add_argument(
            "--flag-missing",
            action="store_true",
            dest="flag_missing",
            help="Set fsi_score=-1 for hexes that had no raster coverage (default: 0.5).",
        )

    def handle(self, *args, **options):
        layer_dir = Path(options["layers"])
        if not layer_dir.is_dir():
            raise CommandError(f"--layers must be a directory: {layer_dir}")

        weights_raw = options["weights"]
        if weights_raw is not None:
            weights = dict(zip(LAYER_NAMES, weights_raw))
            total = sum(weights.values())
            if abs(total - 1.0) > 1e-6:
                raise CommandError(f"Weights must sum to 1.0, got {total:.4f}")
        else:
            weights = {name: 1.0 / len(LAYER_NAMES) for name in LAYER_NAMES}

        rasters = _find_rasters(layer_dir)
        if not rasters:
            raise CommandError(
                f"No recognizable raster files found in {layer_dir}. "
                f"Expected filenames matching: {LAYER_NAMES}"
            )
        self.stdout.write(f"Found rasters: {list(rasters.keys())}")

        # Load all hex centroids
        hexes = list(
            HexCell.objects.only("h3_index", "centroid", "fsi_inputs", "fsi_score")
        )
        if not hexes:
            raise CommandError(
                "No HexCell rows found. Run build_hexgrid first."
            )
        self.stdout.write(f"{len(hexes)} HexCells to process.")

        # (lng, lat) list for rasterio sampling
        coords = [(h.centroid.x, h.centroid.y) for h in hexes]

        # Sample each available layer
        layer_values: dict[str, np.ndarray] = {}
        for name in LAYER_NAMES:
            if name not in rasters:
                self.stdout.write(
                    self.style.WARNING(f"  Layer '{name}' not found — will use 0.")
                )
                layer_values[name] = np.zeros(len(hexes))
                continue
            self.stdout.write(f"  Sampling '{name}' from {rasters[name].name} ...")
            raw = _sample_raster(rasters[name], coords)
            layer_values[name] = _normalize(raw)
            n_nodata = int(np.sum(raw == 0) + np.isnan(raw).sum())
            self.stdout.write(f"    → sampled, nodata/zero count: {n_nodata}")

        # Compute FSI score and write back
        batch_size = options["batch_size"]
        flag_missing = options["flag_missing"]
        covered = 0
        uncovered = 0

        for i in range(0, len(hexes), batch_size):
            batch = hexes[i : i + batch_size]
            for j, cell in enumerate(batch):
                idx = i + j
                fsi_inputs = {
                    name: float(layer_values[name][idx]) for name in LAYER_NAMES
                }
                score = sum(
                    weights[name] * fsi_inputs[name] for name in LAYER_NAMES
                )
                # A hex with all-zero inputs in every layer is likely uncovered
                all_zero = all(v == 0.0 for v in fsi_inputs.values())
                if all_zero and flag_missing:
                    score = -1.0
                    uncovered += 1
                else:
                    covered += 1

                cell.fsi_inputs = fsi_inputs
                cell.fsi_score = round(score, 6)

            HexCell.objects.bulk_update(
                batch, ["fsi_inputs", "fsi_score"], batch_size=batch_size
            )
            self.stdout.write(f"  Updated {min(i + batch_size, len(hexes))}/{len(hexes)}")

        coverage_pct = 100.0 * covered / len(hexes) if hexes else 0
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {covered} hexes with data ({coverage_pct:.1f}%), "
                f"{uncovered} flagged as uncovered."
            )
        )
