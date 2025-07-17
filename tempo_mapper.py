
def match_energy_level(energy: float, target: str) -> bool:
    thresholds = {
        "low": (0.0, 0.3),
        "medium": (0.3, 0.6),
        "high": (0.6, 0.8),
        "very high": (0.8, 1.0),
    }
    low, high = thresholds.get(target, (0.0, 1.0))
    return low <= energy <= high


def select_tracks_for_segment(tracks: list, bpm_range: tuple, energy_target: str, duration_min: float) -> list:
    segment_tracks = []
    total_duration = 0.0

    for t in sorted(tracks, key=lambda x: -x.get("popularity", 50)):
        if not (bpm_range[0] <= t.get("tempo", 0) <= bpm_range[1]):
            continue
        if not match_energy_level(t.get("energy", 0.5), energy_target):
            continue

        duration = t.get("duration_ms", 180000) / 60000  # ms to minutes
        if total_duration + duration > duration_min:
            break

        segment_tracks.append(t)
        total_duration += duration

    return segment_tracks


def build_tempo_mapped_playlist(all_tracks: list, segments: list) -> list:
    full_playlist = []

    for segment in segments:
        bpm_range = segment.get("bpm_range", (0, 300))
        energy = segment.get("energy", "medium")
        duration_min = segment["end_min"] - segment["start_min"]

        segment_tracks = select_tracks_for_segment(
            all_tracks,
            bpm_range=bpm_range,
            energy_target=energy,
            duration_min=duration_min
        )
        full_playlist.extend(segment_tracks)

    return full_playlist
