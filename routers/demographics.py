# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends
# pyrefly: ignore [missing-import]
from sqlmodel import Session, select, func
from core.database import get_session
from core.models import Election, Constituency, Candidate
from core.logic import get_alliance
from typing import List, Dict

router = APIRouter(prefix="/api/v1/demographics", tags=["demographics"])

@router.get("/gender-stats")
def get_gender_stats(session: Session = Depends(get_session)):
    elections = session.exec(select(Election).order_by(Election.year)).all()
    
    gender_trend = []
    total_women_winners = 0
    total_women_candidates = 0
    total_winners = 0
    total_candidates = 0

    for e in elections:
        # Total candidates in this year
        cand_count_stmt = select(func.count(Candidate.id)).join(Constituency).where(Constituency.election_year == e.year)
        count_all = session.exec(cand_count_stmt).one()
        
        # Women candidates
        women_count_stmt = cand_count_stmt.where(Candidate.sex == 'F')
        count_women = session.exec(women_count_stmt).one()
        
        # Success Rate
        # Winners
        winners_stmt = select(Candidate).join(Constituency).where(Constituency.election_year == e.year, Candidate.rank == 1)
        winners = session.exec(winners_stmt).all()
        
        women_winners = [w for w in winners if w.sex == 'F']
        
        gender_trend.append({
            "year": e.year,
            "total_candidates": count_all,
            "women_candidates": count_women,
            "percentage": round((count_women / count_all * 100), 2) if count_all > 0 else 0,
            "women_winners": len(women_winners)
        })
        
        total_women_candidates += count_women
        total_candidates += count_all
        total_women_winners += len(women_winners)
        total_winners += len(winners)

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
    elections = session.exec(select(Election).order_by(Election.year)).all()
    data = []
    for e in elections:
        # Sum of all candidate votes for this election year
        total_votes_stmt = select(func.sum(Candidate.votes)).join(Constituency).where(Constituency.election_year == e.year)
        votes_polled = session.exec(total_votes_stmt).one() or 0
        
        data.append({
            "year": e.year,
            "electorate": e.total_electorate or 0,
            "electorate_crores": round((e.total_electorate or 0) / 10000000, 2),
            "votes_polled": int(votes_polled),
            "votes_crores": round(float(votes_polled) / 10000000, 2),
            "turnout": round((float(votes_polled) / e.total_electorate * 100), 2) if e.total_electorate else 0
        })
    return {"data": data}

@router.get("/party-gender-breakdown")
def get_party_gender_breakdown(session: Session = Depends(get_session)):
    # Major parties analysis
    major_parties = ["CPI(M)", "INC", "CPI", "IUML", "BJP", "KERALA CONGRESS (M)"]
    
    results = []
    for party in major_parties:
        # Total contested
        total_stmt = select(func.count(Candidate.id)).where(Candidate.party.ilike(f"%{party}%"))
        total_contested = session.exec(total_stmt).one()
        
        # Women fielded
        women_stmt = total_stmt.where(Candidate.sex == 'F')
        women_fielded = session.exec(women_stmt).one()
        
        # Seats won by women
        won_stmt = women_stmt.where(Candidate.rank == 1)
        seats_won = session.exec(won_stmt).one()
        
        results.append({
            "party": party,
            "total_contested": total_contested,
            "women_fielded": women_fielded,
            "ratio": round((women_fielded / total_contested * 100), 1) if total_contested > 0 else 0,
            "seats_won": seats_won,
            "trend": "up" if seats_won > 0 else "stable"
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
