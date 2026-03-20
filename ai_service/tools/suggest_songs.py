"""
Tool 2: Song suggestion logic
"""
import sys
import os

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rating import (
    get_cover_url,
    get_rank_info,
    get_next_rank,
    calculate_song_rating,
    calc_rating,
    get_all_songs,
    get_player_data,
    RANK_FACTORS,
)


def suggest_songs(
    player_data: dict,
    all_songs: list,
    target_rating: int = None,
    mode: str = "auto",
    max_suggestions: int = 5,
    difficulty_filter: list = None,
    version: str = "CiRCLE"
) -> dict:
    """
    Suggest songs to improve player rating.
    
    Args:
        player_data: Player data with profile, best, current
        all_songs: All songs from maimai API (musicData)
        target_rating: Target rating to reach (None = maximize)
        max_suggestions: Maximum number of songs to suggest
        difficulty_filter: List of difficulties to include
        version: Game version
    
    Returns:
        Dictionary with suggestions and calculations
    """
    # Build constants lookup
    constants = {}
    for song in all_songs:
        for diff in ["basic", "advanced", "expert", "master", "remaster"]:
            if diff in song:
                key = (song["title"], song["chartType"], diff)
                constants[key] = song[diff].get("constant", 0)
    
    # Get current rating using API
    current_result = calc_rating(player_data, version)
    current_rating = current_result["rating"]["total"]
    
    # Calculate player's current max constant (hardest song they play)
    max_player_constant = 0
    min_player_constant = 999
    for s in player_data.get("best", []) + player_data.get("current", []):
        key = (s.get("title"), s.get("chartType"), s.get("difficulty"))
        c = constants.get(key, 0)
        if c > 0:
            if c > max_player_constant:
                max_player_constant = c
            if c < min_player_constant:
                min_player_constant = c
    
    # Filter new songs to be within player's current difficulty range
    min_constant = min_player_constant
    max_constant = min(max_player_constant, 15.0)
    
    # Get existing songs (title + chartType + difficulty)
    existing = set()
    for song in player_data.get("best", []):
        existing.add((song.get("title"), song.get("chartType"), song.get("difficulty")))
    for song in player_data.get("current", []):
        existing.add((song.get("title"), song.get("chartType"), song.get("difficulty")))
    
    # Get songs player can improve (score < SSS+)
    improvable = {}
    for song in list(player_data.get("best", [])) + list(player_data.get("current", [])):
        key = (song.get("title"), song.get("chartType"), song.get("difficulty"))
        score = song.get("score", 0)
        if score < 1005000:
            improvable[key] = score
    
    # Candidate difficulties
    difficulties = difficulty_filter or ["master", "expert", "advanced"]
    
    # Latest versions (new songs to suggest)
    latest_versions = ["CiRCLE", "PRiSM+"]
    
    # Find new songs (from latest versions, not in best/current)
    candidates = []
    new_song_count = 0
    
    # Get current section song ratings sorted
    rating_songs = []
    for s in player_data.get("current", []):
        key = (s.get("title"), s.get("chartType"), s.get("difficulty"))
        const = constants.get(key, 0)
        if const > 0:
            rating = calculate_song_rating(const, s.get("score", 0))
            rating_songs.append(rating)
    rating_songs.sort()
    
    for song in all_songs:
        version = song.get("releasedVersion", "")
        if version not in latest_versions:
            continue
            
        for diff in difficulties:
            if diff not in song:
                continue
            
            key = (song["title"], song["chartType"], diff)
            if key in existing:
                continue
            
            constant = song[diff].get("constant", 0)
            if constant <= 0:
                continue
            
            if constant < min_constant or constant > max_constant:
                continue
            
            max_rating = calculate_song_rating(constant, 1005000, 0)
            
            replace_idx = new_song_count if new_song_count < len(rating_songs) else len(rating_songs) - 1
            rating_replaced = rating_songs[replace_idx] if replace_idx < len(rating_songs) else 0
            
            min_rating_needed = rating_replaced + 1
            
            min_score_needed = 0
            min_rank_needed = ""
            for ms, factor, rank_name in reversed(RANK_FACTORS):
                potential = int(constant * (ms / 10000) * factor)
                if potential >= min_rating_needed:
                    min_score_needed = ms
                    min_rank_needed = rank_name
                    break
            
            if min_score_needed == 0:
                min_score_needed = 1005000
                min_rank_needed = "SSS+"
            
            target_rank_rating = calculate_song_rating(constant, min_score_needed, 0)
            
            candidates.append({
                "title": song["title"],
                "artist": song.get("artist", ""),
                "chartType": song["chartType"],
                "difficulty": diff,
                "level": song[diff].get("level", ""),
                "constant": constant,
                "version": version,
                "image": song.get("image", ""),
                "cover_url": get_cover_url(song.get("image", "")),
                "max_rating": max_rating,
                "min_rating_needed": min_rating_needed,
                "target_rank": min_rank_needed,
                "target_score": min_score_needed,
                "potential_rating": target_rank_rating,
                "rating_gain": target_rank_rating - rating_replaced,
                "replaces": rating_replaced,
                "type": "new"
            })
            new_song_count += 1
    
    # Find improvement candidates
    improvements = []
    for song in all_songs:
        for diff in difficulties:
            if diff not in song:
                continue
            
            key = (song["title"], song["chartType"], diff)
            if key not in improvable:
                continue
            
            constant = song[diff].get("constant", 0)
            if constant <= 0:
                continue
            
            current_score = improvable[key]
            current_rank, current_pct = get_rank_info(current_score)
            current_pct_str = f"{current_pct:.4f}%"
            current_rating_song = calculate_song_rating(constant, current_score)
            
            target_rank, target_score = get_next_rank(current_score)
            potential_rating = calculate_song_rating(constant, target_score, int(constant * 100))
            rating_gain = potential_rating - current_rating_song
            
            if rating_gain > 0:
                improvements.append({
                    "title": song["title"],
                    "artist": song.get("artist", ""),
                    "chartType": song["chartType"],
                    "difficulty": diff,
                    "level": song[diff].get("level", ""),
                    "constant": constant,
                    "image": song.get("image", ""),
                    "cover_url": get_cover_url(song.get("image", "")),
                    "current_score": current_score,
                    "current_rank": current_rank,
                    "current_pct": current_pct,
                    "current_pct_str": current_pct_str,
                    "target_rank": target_rank,
                    "target_score": target_score,
                    "potential_rating": potential_rating,
                    "rating_gain": rating_gain,
                    "type": "improve"
                })
    
    candidates.sort(key=lambda x: x["potential_rating"], reverse=True)
    improvements.sort(key=lambda x: x["rating_gain"], reverse=True)
    
    is_target_mode = mode == "target" or (mode == "auto" and target_rating is not None)
    
    suggestions = {
        "mode": "target" if is_target_mode else "best_effort",
        "current_rating": current_rating,
        "target_rating": target_rating,
    }
    
    if is_target_mode:
        rating_needed = target_rating - current_rating
        
        rating_songs = []
        for s in player_data.get("best", []) + player_data.get("current", []):
            key = (s.get("title"), s.get("chartType"), s.get("difficulty"))
            const = constants.get(key, 0)
            if const > 0:
                rating = calculate_song_rating(const, s.get("score", 0))
                rating_songs.append(rating)
        rating_songs.sort()
        
        all_song_options = []
        
        for s in improvements:
            constant = s.get("constant", 0)
            if constant <= 0:
                continue
            max_rating = calculate_song_rating(constant, 1005000, 0)
            current_rating_song = s.get("potential_rating", 0) - s.get("rating_gain", 0)
            all_song_options.append({
                "title": s["title"],
                "artist": s.get("artist", ""),
                "level": s.get("level", ""),
                "image": s.get("image", ""),
                "constant": constant,
                "difficulty": s.get("difficulty", ""),
                "chartType": s.get("chartType", ""),
                "current_rating": current_rating_song,
                "current_score": s.get("current_score", 0),
                "current_rank": s.get("current_rank", ""),
                "current_pct": s.get("current_pct", 0),
                "current_pct_str": s.get("current_pct_str", "0.0000%"),
                "max_rating": max_rating,
                "type": "improve"
            })
        
        for s in candidates:
            constant = s.get("constant", 0)
            if constant <= 0:
                continue
            max_rating = calculate_song_rating(constant, 1005000, 0)
            idx = len([x for x in all_song_options if x["type"] == "new"]) % len(rating_songs) if rating_songs else 0
            replace_rating = rating_songs[idx] if idx < len(rating_songs) else 0
            all_song_options.append({
                "title": s.get("title", ""),
                "artist": s.get("artist", ""),
                "level": s.get("level", ""),
                "image": s.get("image", ""),
                "version": s.get("version", ""),
                "constant": constant,
                "difficulty": s.get("difficulty", ""),
                "chartType": s.get("chartType", ""),
                "current_rating": replace_rating,
                "max_rating": max_rating,
                "type": "new"
            })
        
        songs_to_replace = 50
        gain_per_song_needed = rating_needed / songs_to_replace
        
        avg_current = sum(rating_songs) / len(rating_songs) if rating_songs else 0
        
        min_gain_needed = max(10, int(gain_per_song_needed))
        all_song_options = [s for s in all_song_options if s["max_rating"] - avg_current >= min_gain_needed]
        
        all_song_options.sort(key=lambda x: (x["constant"], -(x["max_rating"] - x["current_rating"])))
        
        selected = []
        remaining = rating_needed
        
        for song_opt in all_song_options:
            if remaining <= 0:
                break
            
            current_r = song_opt["current_rating"]
            max_r = song_opt["max_rating"]
            
            potential_gain = max_r - current_r
            
            if potential_gain <= 0:
                continue
            
            actual_gain = min(potential_gain, remaining)
            target_r = current_r + actual_gain
            
            min_score = 0
            min_rank = ""
            for ms, factor, rank_name in RANK_FACTORS:
                potential = int(song_opt["constant"] * (ms / 10000) * factor)
                if potential >= target_r:
                    min_score = ms
                    min_rank = rank_name
                    break
            
            if min_score == 0:
                min_score = 1005000
                min_rank = "SSS+"
            
            selected.append({
                "song": {
                    "title": song_opt["title"],
                    "artist": song_opt.get("artist", ""),
                    "level": song_opt.get("level", ""),
                    "image": song_opt.get("image", ""),
                    "cover_url": get_cover_url(song_opt.get("image", "")),
                    "version": song_opt.get("version", ""),
                    "difficulty": song_opt["difficulty"],
                    "chartType": song_opt["chartType"],
                    "constant": song_opt["constant"],
                    "target_rank": min_rank,
                    "target_score": min_score,
                    "achievement": round(min_score / 10000, 2),
                    "potential_rating": target_r,
                },
                "gain_needed": actual_gain,
                "max_gain": potential_gain,
                "type": song_opt["type"],
                "current_score": song_opt.get("current_score", 0),
                "current_rank": song_opt.get("current_rank", ""),
                "current_pct_str": song_opt.get("current_pct_str", ""),
            })
            
            remaining -= actual_gain
        
        projected = current_rating + sum(s["gain_needed"] for s in selected)
        
        suggestions["rating_needed"] = rating_needed
        suggestions["songs"] = selected
        suggestions["projected_rating"] = projected
        suggestions["message"] = f"Here's the easiest path to reach {target_rating}! (+{sum(s['gain_needed'] for s in selected)} rating from {len(selected)} songs)"
    else:
        improvements_sorted = sorted(improvements, key=lambda x: x["rating_gain"])
        
        suggestions["improvements"] = improvements_sorted[:max_suggestions]
        suggestions["new_songs"] = candidates[:max_suggestions]
        suggestions["message"] = f"Found {len(candidates)} new songs and {len(improvements)} improvements"
    
    return suggestions


if __name__ == "__main__":
    import json
    
    # Load player data
    player_data = get_player_data()
    
    # Check if error
    if "error" in player_data:
        print("ERROR:", player_data["error"])
        print("\nInstructions:")
        for line in player_data.get("instructions", []):
            print(line)
        exit(1)
    
    # Load all songs (from API or local fallback)
    all_songs = get_all_songs()
    
    # Test best_effort mode
    print("=== BEST EFFORT MODE ===")
    result = suggest_songs(player_data, all_songs, mode="best_effort", max_suggestions=5)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    print("\n=== TARGET MODE (15000) ===")
    result = suggest_songs(player_data, all_songs, target_rating=15000, mode="target")
    print(json.dumps(result, indent=2, ensure_ascii=False))
