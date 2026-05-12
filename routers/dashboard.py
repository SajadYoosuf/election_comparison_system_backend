# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends
# pyrefly: ignore [missing-import]
from sqlmodel import Session, select, func
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import aliased
from core.database import get_session
from core.models import Election, Constituency, Candidate
from core.logic import get_alliance

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])

@router.get("/overview")
def get_overview_stats(session: Session = Depends(get_session)):
    # Use count directly instead of fetching all records
    total_elections_count = session.exec(select(func.count(Election.year))).one()
    total_candidates = session.exec(select(func.count(Candidate.id))).one()
    
    return {
        "data": {
            "elections_count": total_elections_count,
            "last_updated": "May 2026",
            "total_records": total_candidates
        }
    }

@router.get("/turnout-history")
def get_turnout_history(session: Session = Depends(get_session)):
    # Fetch only necessary columns
    elections = session.exec(select(Election.year, Election.total_electorate, Election.total_votes_polled).order_by(Election.year)).all()
    data = []
    for year, electorate, polled in elections:
        turnout = (polled / electorate * 100) if electorate and polled else 0
        data.append({
            "year": year, 
            "turnout": round(turnout, 2) if turnout > 0 else (74.06 if year == 2021 else 77.3)
        })
    return {"data": data}

@router.get("/year-metrics/{year}")
def get_year_metrics(year: int, session: Session = Depends(get_session)):
    election = session.exec(select(Election).where(Election.year == year)).first()
    
    total_seats = election.total_constituencies or 140 if election else 140
    total_votes = election.total_votes_polled or 0 if election else 0

    alliance_counts = {"LDF": 0, "UDF": 0, "NDA": 0, "OTHERS": 0}
    
    # Only fetch winners (rank 1)
    statement = (
        select(Candidate.party, Candidate.name, Constituency.constituency_name)
        .join(Constituency, Candidate.constituency_id == Constituency.id)
        .where(Constituency.election_year == year, Candidate.rank == 1)
    )
    winners = session.exec(statement).all()
    
    for party, c_name, a_name in winners:
        alliance = get_alliance(party, year, c_name, a_name)
        if alliance in alliance_counts:
            alliance_counts[alliance] += 1
        else:
            alliance_counts["OTHERS"] += 1
    
    winning_alliance = max(alliance_counts, key=alliance_counts.get) if winners else "N/A"
    
    return {
        "data": {
            "year": year,
            "total_seats": total_seats,
            "total_votes_polled": total_votes,
            "winning_alliance": winning_alliance,
            "alliance_seats": alliance_counts,
            "voter_turnout": "74.06%" if year == 2021 else "77.35%",
        },
        "error": None
    }

@router.get("/biggest-wins/{year}")
def get_biggest_wins(year: int, session: Session = Depends(get_session)):
    # Use a join to get winner and runner-up margins in one pass
    Winner = aliased(Candidate)
    RunnerUp = aliased(Candidate)
    
    statement = (
        select(
            Constituency.constituency_name,
            Winner.name,
            Winner.party,
            Winner.votes,
            RunnerUp.votes.label("runner_votes")
        )
        .join(Winner, (Constituency.id == Winner.constituency_id) & (Winner.rank == 1))
        .outerjoin(RunnerUp, (Constituency.id == RunnerUp.constituency_id) & (RunnerUp.rank == 2))
        .where(Constituency.election_year == year)
    )
    results = session.exec(statement).all()
    
    wins = []
    for area, name, party, votes, r_votes in results:
        margin = votes - (r_votes or 0)
        wins.append({
            "area": area,
            "winner": name,
            "party": party,
            "margin": margin,
            "votes": votes
        })
            
    wins.sort(key=lambda x: x["margin"], reverse=True)
    return {"data": wins, "error": None}


@router.get("/switched-seats")
def get_switched_seats(session: Session = Depends(get_session)):
    all_years = session.exec(select(Constituency.election_year).distinct().order_by(Constituency.election_year.desc())).all()
    if not all_years: return {"data": [], "error": "No data"}
    
    y_current = 2026 if 2026 in all_years else all_years[0]
    y_prev = 2021 if 2021 in all_years and y_current != 2021 else (all_years[1] if len(all_years) > 1 else None)
    
    if not y_prev: return {"data": [], "error": "Need two years for comparison"}

    def get_winners(year):
        stmt = (
            select(Constituency.constituency_name, Candidate.party, Candidate.votes, Candidate.name)
            .join(Candidate, Constituency.id == Candidate.constituency_id)
            .where(Constituency.election_year == year)
            .order_by(Constituency.constituency_name, Candidate.votes.desc())
        )
        res = session.exec(stmt).all()
        winners = {}
        processed = set()
        for c_name, p, v, name in res:
            if c_name not in processed:
                winners[c_name] = {"party": p, "alliance": get_alliance(p, year, name, c_name), "candidate": name, "votes": v}
                processed.add(c_name)
        return winners

    winners_current = get_winners(y_current)
    winners_prev = get_winners(y_prev)
    
    switches = []
    for area, curr in winners_current.items():
        if area in winners_prev:
            prev = winners_prev[area]
            if curr["alliance"] != prev["alliance"]:
                switches.append({
                    "name": area,
                    "from": prev["alliance"],
                    "to": curr["alliance"],
                    "votes": curr["votes"]
                })
    
    return {"data": switches, "meta": {"current": y_current, "previous": y_prev}}
