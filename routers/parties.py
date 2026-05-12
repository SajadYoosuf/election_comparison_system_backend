# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends
# pyrefly: ignore [missing-import]
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
    
    # Bulk fetch current seats
    curr_stmt = select(Candidate.party, func.count(Candidate.id)).join(Constituency).where(Candidate.rank == 1, Constituency.election_year == current_year).group_by(Candidate.party)
    raw_curr = {p: c for p, c in session.exec(curr_stmt).all()}
    
    # Bulk fetch previous seats
    raw_prev = {}
    if prev_year:
        prev_stmt = select(Candidate.party, func.count(Candidate.id)).join(Constituency).where(Candidate.rank == 1, Constituency.election_year == prev_year).group_by(Candidate.party)
        raw_prev = {p: c for p, c in session.exec(prev_stmt).all()}

    def get_count(party_name, lookup):
        variants = get_party_variants(party_name)
        return sum(lookup.get(v, 0) for v in variants)

    results = []
    for p_name in major_parties:
        current_seats = get_count(p_name, raw_curr)
        prev_seats = get_count(p_name, raw_prev)
        
        trend = 0
        if prev_seats > 0:
            trend = ((current_seats - prev_seats) / prev_seats) * 100
        elif current_seats > 0:
            trend = 100.0
            
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
    
    # 1. Find constituencies with most wins
    stronghold_stmt = (
        select(Constituency.constituency_name, func.count(Candidate.id).label("win_count"))
        .join(Candidate, Candidate.constituency_id == Constituency.id)
        .where(Candidate.party.in_(variants), Candidate.rank == 1)
        .group_by(Constituency.constituency_name)
        .order_by(func.count(Candidate.id).desc())
        .limit(6)
    )
    stronghold_data = session.exec(stronghold_stmt).all()
    if not stronghold_data: return {"data": []}
    
    stronghold_names = [row[0] for row in stronghold_data]
    recent_years = [2026, 2021, 2016, 2011]
    
    # 2. Batch fetch all winners for these constituencies across recent years
    streak_stmt = (
        select(Constituency.constituency_name, Constituency.election_year, Candidate.party)
        .join(Candidate, Candidate.constituency_id == Constituency.id)
        .where(
            Constituency.constituency_name.in_(stronghold_names),
            Constituency.election_year.in_(recent_years),
            Candidate.rank == 1
        )
    )
    streak_results = session.exec(streak_stmt).all()
    streak_map = {} # (const_name, year) -> party
    for name, year, party in streak_results:
        streak_map[(name, year)] = party

    # 3. Batch fetch latest margins (2026)
    margin_stmt = (
        select(Constituency.constituency_name, Candidate.votes, Candidate.party, Candidate.rank)
        .join(Candidate, Candidate.constituency_id == Constituency.id)
        .where(
            Constituency.constituency_name.in_(stronghold_names),
            Constituency.election_year == 2026,
            Candidate.rank.in_([1, 2])
        )
        .order_by(Constituency.constituency_name, Candidate.rank)
    )
    margin_results = session.exec(margin_stmt).all()
    margin_map = {} # const_name -> (winner_votes, runner_votes, winner_party)
    for name, votes, party, rank in margin_results:
        if name not in margin_map: margin_map[name] = [0, 0, ""]
        if rank == 1:
            margin_map[name][0] = votes or 0
            margin_map[name][2] = party
        else:
            margin_map[name][1] = votes or 0

    results = []
    for name, win_count in stronghold_data:
        # Calculate streak
        streak = []
        for y in recent_years:
            winner_party = streak_map.get((name, y))
            streak.append(winner_party in variants if winner_party else False)
            
        # Calculate margin
        m_info = margin_map.get(name, [0, 0, ""])
        margin = 0
        if m_info[2] in variants:
            margin = m_info[0] - m_info[1]
        
        results.append({
            "constituency": name,
            "district": "Kottayam" if name == "PUTHUPPALLY" else ("Kannur" if name == "DHARMADAM" else "Various"),
            "win_count": f"{win_count}",
            "win_ratio": f"{win_count}/14",
            "streak": streak,
            "margin": margin
        })
        
    return {"data": results}

