# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends
# pyrefly: ignore [missing-import]
from sqlmodel import Session, select, func, case, or_
from core.database import get_session
from core.models import Election, Constituency, Candidate
from core.logic import get_alliance
from typing import List, Dict

router = APIRouter(prefix="/api/v1/demographics", tags=["demographics"])

@router.get("/gender-stats")
def get_gender_stats(session: Session = Depends(get_session)):
    # 1. Total and Female candidate counts per year
    cand_stats_stmt = (
        select(
            Constituency.election_year,
            func.count(Candidate.id).label("total"),
            func.sum(case((Candidate.sex == 'F', 1), else_=0)).label("women")
        )
        .join(Constituency, Candidate.constituency_id == Constituency.id)
        .group_by(Constituency.election_year)
        .order_by(Constituency.election_year)
    )
    cand_stats = session.exec(cand_stats_stmt).all()
    
    # 2. Women winners per year
    winners_stats_stmt = (
        select(
            Constituency.election_year,
            func.count(Candidate.id).label("women_winners")
        )
        .join(Constituency, Candidate.constituency_id == Constituency.id)
        .where(Candidate.rank == 1, Candidate.sex == 'F')
        .group_by(Constituency.election_year)
    )
    winners_stats = {row[0]: row[1] for row in session.exec(winners_stats_stmt).all()}

    gender_trend = []
    total_women_winners = 0
    total_women_candidates = 0
    total_winners = 0
    total_candidates = 0

    # Total winners is easy (140 per election usually)
    # But we calculate it from cand_stats for consistency
    for year, total, women in cand_stats:
        w_winners = winners_stats.get(year, 0)
        
        gender_trend.append({
            "year": year,
            "total_candidates": total,
            "women_candidates": int(women),
            "percentage": round((float(women) / total * 100), 2) if total > 0 else 0,
            "women_winners": w_winners
        })
        
        total_women_candidates += int(women)
        total_candidates += total
        total_women_winners += w_winners
        # We assume 140 seats per modern election or dynamic count
        # For Kerala, it's 140 since 1977
        total_winners += 140 if year >= 1977 else 126 

    # Success Parity calculation
    men_win_rate = ((total_winners - total_women_winners) / (total_candidates - total_women_candidates) * 100) if (total_candidates - total_women_candidates) > 0 else 0
    women_win_rate = (total_women_winners / total_women_candidates * 100) if total_women_candidates > 0 else 0

    return {
        "data": {
            "trend": gender_trend,
            "parity": {
                "men_win_rate": round(men_win_rate, 1),
                "women_win_rate": round(women_win_rate, 1)
            }
        }
    }

@router.get("/electorate-growth")
def get_electorate_growth(session: Session = Depends(get_session)):
    # Join Election and Candidate to get votes polled in one aggregation
    stats_stmt = (
        select(
            Election.year,
            Election.total_electorate,
            func.sum(Candidate.votes).label("total_votes")
        )
        .join(Constituency, Election.year == Constituency.election_year)
        .join(Candidate, Constituency.id == Candidate.constituency_id)
        .group_by(Election.year, Election.total_electorate)
        .order_by(Election.year)
    )
    stats = session.exec(stats_stmt).all()
    
    data = []
    for year, electorate, votes_polled in stats:
        data.append({
            "year": year,
            "electorate": electorate or 0,
            "electorate_crores": round((electorate or 0) / 10000000, 2),
            "votes_polled": int(votes_polled),
            "votes_crores": round(float(votes_polled) / 10000000, 2),
            "turnout": round((float(votes_polled) / electorate * 100), 2) if electorate else 0
        })
    return {"data": data}

@router.get("/party-gender-breakdown")
def get_party_gender_breakdown(session: Session = Depends(get_session)):
    major_parties = ["CPI(M)", "INC", "CPI", "IUML", "BJP", "KERALA CONGRESS (M)"]
    
    # Aggregated query for all major parties
    # We use a case statement for the specific parties to group them cleanly
    stats_stmt = (
        select(
            Candidate.party,
            func.count(Candidate.id).label("total"),
            func.sum(case((Candidate.sex == 'F', 1), else_=0)).label("women"),
            func.sum(case(((Candidate.sex == 'F') & (Candidate.rank == 1), 1), else_=0)).label("won")
        )
        .where(or_(*[Candidate.party.ilike(f"%{p}%") for p in major_parties]))
        .group_by(Candidate.party)
    )
    
    # Process results into standardized buckets
    raw_results = session.exec(stats_stmt).all()
    party_buckets = {p: {"total": 0, "women": 0, "won": 0} for p in major_parties}
    
    for party_name, total, women, won in raw_results:
        for p in major_parties:
            if p.lower() in party_name.lower():
                party_buckets[p]["total"] += total
                party_buckets[p]["women"] += int(women)
                party_buckets[p]["won"] += int(won)
                break

    results = []
    for party, stats in party_buckets.items():
        results.append({
            "party": party,
            "total_contested": stats["total"],
            "women_fielded": stats["women"],
            "ratio": round((stats["women"] / stats["total"] * 100), 1) if stats["total"] > 0 else 0,
            "seats_won": stats["won"],
            "trend": "up" if stats["won"] > 0 else "stable"
        })
        
    return {"data": results}


@router.get("/advanced-insights")
def get_advanced_insights(session: Session = Depends(get_session)):
    # 1. District-wise Women Representation (Strongholds)
    # Since 'district' is not in the DB, we use a mapping for major constituencies
    # and aggregate in Python for this analytical view.
    district_map = {
        "DHARMADAM": "Kannur", "KANNUR": "Kannur", "THALASSERY": "Kannur",
        "PUTHUPPALLY": "Kottayam", "POONJAR": "Kottayam", "KOTTAYAM": "Kottayam",
        "VATTITYOORKAVU": "Thiruvananthapuram", "NEMOM": "Thiruvananthapuram", "THIRUVANANTHAPURAM": "Thiruvananthapuram",
        "ERNAKULAM": "Ernakulam", "THRIKKAKARA": "Ernakulam", "KOCHI": "Ernakulam",
        "THRISSUR": "Thrissur", "GURUVAYUR": "Thrissur", "IRINJALAKUDA": "Thrissur",
        "KOZHIKODE NORTH": "Kozhikode", "BEYPORE": "Kozhikode",
        "MALAPPURAM": "Malappuram", "PERINTHALMANNA": "Malappuram"
    }
    
    # Fetch all women winners
    winners = session.exec(
        select(Candidate, Constituency.constituency_name)
        .join(Constituency)
        .where(Candidate.sex == 'F', Candidate.rank == 1)
    ).all()
    
    district_counts = {}
    for cand, name in winners:
        norm_name = name.strip().upper()
        # Find district from map or default to 'Other'
        d = district_map.get(norm_name, "Other")
        district_counts[d] = district_counts.get(d, 0) + 1
    
    strongholds = [{"district": k, "winners": v} for k, v in district_counts.items() if k != "Other"]

    # 2. Vote Share Gap
    avg_vote_share_women = session.exec(
        select(func.avg(Candidate.vote_percentage)).where(Candidate.sex == 'F')
    ).one() or 0
    
    avg_vote_share_men = session.exec(
        select(func.avg(Candidate.vote_percentage)).where(Candidate.sex == 'M')
    ).one() or 0

    return {
        "data": {
            "strongholds": sorted(strongholds, key=lambda x: x["winners"], reverse=True),
            "vote_share_gap": {
                "women": round(float(avg_vote_share_women), 2),
                "men": round(float(avg_vote_share_men), 2)
            }
        }
    }
