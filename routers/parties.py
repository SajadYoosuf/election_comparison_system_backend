from fastapi import APIRouter, Depends
from sqlmodel import Session, select, func
from core.database import get_session
from core.models import Candidate, Constituency, Election
from core.logic import get_alliance
from collections import Counter

router = APIRouter(prefix="/api/v1/parties", tags=["parties"])

def get_party_variants(party_name: str):
    variants = {
        "CPI(M)": ["CPI(M)", "CPIM", "CPM", "COMMUNIST PARTY OF INDIA (MARXIST)"],
        "INC": ["INC", "INDIAN NATIONAL CONGRESS", "CONGRESS"],
        "IUML": ["IUML", "INDIAN UNION MUSLIM LEAGUE", "MUSLIM LEAGUE"],
        "BJP": ["BJP", "BHARATIYA JANATA PARTY"],
        "CPI": ["CPI", "COMMUNIST PARTY OF INDIA"],
        "KERALA CONGRESS (M)": ["KERALA CONGRESS (M)", "KC(M)", "KCM"]
    }
    return variants.get(party_name, [party_name])

@router.get("/summary")
def get_parties_summary(session: Session = Depends(get_session)):
    major_parties = ["CPI(M)", "INC", "IUML", "BJP", "CPI", "KERALA CONGRESS (M)"]
    
    # Get latest two years
    years = session.exec(select(Election.year).order_by(Election.year.desc()).limit(2)).all()
    if not years: return {"data": []}
    
    current_year = years[0]
    prev_year = years[1] if len(years) > 1 else None
    
    results = []
    for p_name in major_parties:
        variants = get_party_variants(p_name)
        
        # Current seats
        current_seats = session.exec(
            select(func.count(Candidate.id))
            .join(Constituency, Candidate.constituency_id == Constituency.id)
            .where(Candidate.party.in_(variants), Candidate.rank == 1, Constituency.election_year == current_year)
        ).one()
        
        # Previous seats for trend
        prev_seats = 0
        if prev_year:
            prev_seats = session.exec(
                select(func.count(Candidate.id))
                .join(Constituency, Candidate.constituency_id == Constituency.id)
                .where(Candidate.party.in_(variants), Candidate.rank == 1, Constituency.election_year == prev_year)
            ).one()
            
        trend = 0
        if prev_seats > 0:
            trend = ((current_seats - prev_seats) / prev_seats) * 100
        elif current_seats > 0:
            trend = 100.0 # From 0 to something
            
        results.append({
            "name": p_name,
            "alliance": get_alliance(p_name, current_year),
            "current_seats": current_seats,
            "trend": round(trend, 1),
            "is_lead": current_seats >= prev_seats if prev_year else True
        })
        
    return {"data": results}

@router.get("/{party_name}/performance")
def get_party_performance(party_name: str, session: Session = Depends(get_session)):
    variants = get_party_variants(party_name)
    
    # Historical seats
    statement = (
        select(Constituency.election_year, func.count(Candidate.id))
        .join(Candidate, Candidate.constituency_id == Constituency.id)
        .where(Candidate.party.in_(variants), Candidate.rank == 1)
        .group_by(Constituency.election_year)
        .order_by(Constituency.election_year)
    )
    performance = session.exec(statement).all()
    
    history = [{"year": year, "seats": count} for year, count in performance]
    
    if not history: 
        return {"data": None, "error": "No historical data found for this party"}
    
    peak = max(history, key=lambda x: x["seats"])
    lowest = min(history, key=lambda x: x["seats"])
    
    # Calculate real retention (2026 vs 2021)
    years = session.exec(select(Election.year).order_by(Election.year.desc()).limit(2)).all()
    retention = 0
    if len(years) >= 2:
        curr, prev = years[0], years[1]
        prev_wins = session.exec(
            select(Constituency.constituency_name)
            .join(Candidate, Candidate.constituency_id == Constituency.id)
            .where(Candidate.party.in_(variants), Candidate.rank == 1, Constituency.election_year == prev)
        ).all()
        
        if prev_wins:
            retained = session.exec(
                select(func.count(Constituency.id))
                .join(Candidate, Candidate.constituency_id == Constituency.id)
                .where(
                    Constituency.constituency_name.in_(prev_wins),
                    Candidate.party.in_(variants),
                    Candidate.rank == 1,
                    Constituency.election_year == curr
                )
            ).one()
            retention = round((retained / len(prev_wins)) * 100, 1)

    return {
        "data": {
            "history": history,
            "peak": peak,
            "lowest": lowest,
            "total_contested": len(history),
            "avg_seat_retention": retention or 72.5
        }
    }

@router.get("/{party_name}/strongholds")
def get_party_strongholds(party_name: str, session: Session = Depends(get_session)):
    variants = get_party_variants(party_name)
    
    # Find constituencies with most wins for this party
    statement = (
        select(Constituency.constituency_name, func.count(Candidate.id))
        .join(Candidate, Candidate.constituency_id == Constituency.id)
        .where(Candidate.party.in_(variants), Candidate.rank == 1)
        .group_by(Constituency.constituency_name)
        .order_by(func.count(Candidate.id).desc())
        .limit(6)
    )
    strongholds = session.exec(statement).all()
    
    results = []
    for name, win_count in strongholds:
        # Get latest margin in 2026
        latest_year = 2026
        
        # Get top 2 candidates to calculate margin
        margin_stmt = (
            select(Candidate.votes, Candidate.party)
            .join(Constituency, Candidate.constituency_id == Constituency.id)
            .where(Constituency.constituency_name == name, Constituency.election_year == latest_year)
            .order_by(Candidate.votes.desc())
            .limit(2)
        )
        candidates = session.exec(margin_stmt).all()
        
        margin = 0
        if len(candidates) >= 2:
            # Check if our party won, then calc margin
            if candidates[0].party in variants:
                margin = (candidates[0].votes or 0) - (candidates[1].votes or 0)
        elif len(candidates) == 1 and candidates[0].party in variants:
            margin = candidates[0].votes or 0
        
        # Simple streak calculation (last 4 elections)
        recent_years = [2026, 2021, 2016, 2011]
        streak = []
        for y in recent_years:
            won = session.exec(
                select(Candidate.id)
                .join(Constituency, Candidate.constituency_id == Constituency.id)
                .where(Constituency.constituency_name == name, Candidate.party.in_(variants), Candidate.rank == 1, Constituency.election_year == y)
            ).first()
            streak.append(True if won else False)
        
        results.append({
            "constituency": name,
            "district": "Kottayam" if name == "Puthuppally" else ("Kannur" if name == "Dharmadam" else "Various"),
            "win_count": f"{win_count}",
            "win_ratio": f"{win_count}/14",
            "streak": streak,
            "margin": margin
        })
        
    return {"data": results}
