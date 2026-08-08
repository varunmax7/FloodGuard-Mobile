import { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'

interface Props {
  style?: string
  center?: [number, number]
  zoom?: number
  className?: string
  onMapReady?: (map: maplibregl.Map) => void
}

const DEFAULT_STYLE = 'https://tiles.openfreemap.org/styles/liberty'
// TG + AP combined centre (Vijayawada area). Zoom 6.8 fits both states in a
// laptop viewport. MapLibre uses [lng, lat].
const REGION_CENTER: [number, number] = [80.0000, 16.5000]
const REGION_ZOOM = 6.8

export default function MapPanel({
  style = DEFAULT_STYLE,
  center = REGION_CENTER,
  zoom = REGION_ZOOM,
  className = 'w-full h-full min-h-[400px] rounded-xl',
  onMapReady,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef       = useRef<maplibregl.Map | null>(null)

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const map = new maplibregl.Map({
      container: containerRef.current,
      style,
      center,
      zoom,
    })

    map.addControl(new maplibregl.NavigationControl(), 'top-right')
    map.on('load', () => onMapReady?.(map))
    mapRef.current = map

    return () => { map.remove(); mapRef.current = null }
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  return <div ref={containerRef} className={className} />
}
