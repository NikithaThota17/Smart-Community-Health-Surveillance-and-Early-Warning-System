def compute_personal_risk(complaint):
    """
    Lightweight personal-risk scoring for citizen submissions.
    Returns tuple: (score_0_to_100, level, guidance_line)
    """
    score = 0.0

    # Core symptom burden
    score += min(complaint.symptom_count * 6.0, 36.0)
    if complaint.has_breathing_difficulty:
        score += 24.0
    if complaint.has_fever:
        score += 8.0
    if complaint.has_diarrhea:
        score += 7.0
    if complaint.has_vomiting:
        score += 7.0

    # Environmental exposure
    if complaint.unsafe_drinking_water:
        score += 8.0
    if complaint.water_contamination:
        score += 8.0
    if complaint.nearby_illness_cases:
        score += 6.0
    if complaint.stagnant_water or complaint.garbage_dumping:
        score += 4.0

    score = max(0.0, min(score, 100.0))

    if score >= 70.0:
        level = 'high'
        guidance = "High personal risk: consult doctor/PHC as early as possible."
    elif score >= 40.0:
        level = 'medium'
        guidance = "Medium personal risk: monitor symptoms closely and contact ASHA worker if worsening."
    else:
        level = 'low'
        guidance = "Low personal risk: continue precautions and monitor for any symptom changes."

    return round(score, 2), level, guidance
