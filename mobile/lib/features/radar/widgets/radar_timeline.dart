/// Horizontal timeline scrubber — frame chips + play/pause.
library;

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../../data/models/radar_frame.dart';
import '../../../design/theme/app_theme.dart';

class RadarTimeline extends StatefulWidget {
  final List<RadarFrame> frames;
  final int selectedIndex;
  final bool isPlaying;
  final ValueChanged<int> onFrameSelected;
  final VoidCallback onPlayPause;

  const RadarTimeline({
    super.key,
    required this.frames,
    required this.selectedIndex,
    required this.isPlaying,
    required this.onFrameSelected,
    required this.onPlayPause,
  });

  @override
  State<RadarTimeline> createState() => _RadarTimelineState();
}

class _RadarTimelineState extends State<RadarTimeline> {
  final _scrollCtrl = ScrollController();
  static final _timeFmt = DateFormat('HH:mm');

  @override
  void dispose() {
    _scrollCtrl.dispose();
    super.dispose();
  }

  @override
  void didUpdateWidget(RadarTimeline old) {
    super.didUpdateWidget(old);
    if (old.selectedIndex != widget.selectedIndex) {
      _scrollToSelected();
    }
  }

  void _scrollToSelected() {
    const chipW = 56.0 + 8.0;
    final offset = widget.selectedIndex * chipW - 80;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || !_scrollCtrl.hasClients) return;
      final max = _scrollCtrl.position.maxScrollExtent;
      _scrollCtrl.animateTo(
        offset.clamp(0.0, max),
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOut,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(0, 10, 0, 10),
      decoration: const BoxDecoration(
        color: AppColors.glass,
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        boxShadow: [
          BoxShadow(
            color: Color(0x1A0F172A),
            blurRadius: 12,
            offset: Offset(0, -2),
          ),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // drag handle
          Container(
            width: 36,
            height: 4,
            margin: const EdgeInsets.only(bottom: 10),
            decoration: BoxDecoration(
              color: AppColors.textMuted.withAlpha(80),
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          Row(
            children: [
              const SizedBox(width: 8),
              // Play / pause button
              Material(
                color: AppColors.blue600,
                borderRadius: const BorderRadius.all(Radius.circular(24)),
                child: InkWell(
                  borderRadius: const BorderRadius.all(Radius.circular(24)),
                  onTap: widget.onPlayPause,
                  child: Padding(
                    padding: const EdgeInsets.all(10),
                    child: Icon(
                      widget.isPlaying ? Icons.pause : Icons.play_arrow,
                      color: Colors.white,
                      size: 22,
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              // Frame chips
              Expanded(
                child: SizedBox(
                  height: 40,
                  child: ListView.separated(
                    controller: _scrollCtrl,
                    scrollDirection: Axis.horizontal,
                    itemCount: widget.frames.length,
                    separatorBuilder: (_, __) => const SizedBox(width: 6),
                    itemBuilder: (context, i) {
                      final selected = i == widget.selectedIndex;
                      final frame = widget.frames[i];
                      final local = frame.ts.toLocal();
                      return GestureDetector(
                        onTap: () => widget.onFrameSelected(i),
                        child: AnimatedContainer(
                          duration: const Duration(milliseconds: 180),
                          width: 56,
                          alignment: Alignment.center,
                          decoration: BoxDecoration(
                            color: selected
                                ? AppColors.blue600
                                : AppColors.blue600.withAlpha(20),
                            borderRadius: BorderRadius.circular(20),
                            border: Border.all(
                              color: selected
                                  ? AppColors.blue600
                                  : Colors.transparent,
                              width: 1.5,
                            ),
                          ),
                          child: Text(
                            _timeFmt.format(local),
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              color: selected
                                  ? Colors.white
                                  : AppColors.blue600,
                            ),
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ),
              const SizedBox(width: 8),
            ],
          ),
          const SizedBox(height: 4),
          // Selected timestamp label
          if (widget.frames.isNotEmpty)
            Text(
              _fullLabel(widget.frames[widget.selectedIndex].ts.toLocal()),
              style: const TextStyle(
                fontSize: 11,
                color: AppColors.textMuted,
                fontWeight: FontWeight.w500,
              ),
            ),
        ],
      ),
    );
  }

  String _fullLabel(DateTime dt) =>
      DateFormat('dd MMM yyyy · HH:mm').format(dt);
}
