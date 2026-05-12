# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException
# pyrefly: ignore [missing-import]
from sqlmodel import Session, select
from core.database import get_session
from core.models import Constituency, Candidate, Election
from core.logic import get_alliance

router = APIRouter(prefix="/api/v1", tags=["constituencies"])

@router.get("/elections/{year}")
def get_election_by_year(year: int, session: Session = Depends(get_session)):
    statement = select(Constituency).where(Constituency.election_year == year)
    constituencies = session.exec(statement).all()
    
    formatted_data = []
    for const in constituencies:
        candidates_stmt = select(Candidate).where(Candidate.constituency_id == const.id).order_by(Candidate.votes.desc())
        candidates = session.exec(candidates_stmt).all()
        
        results = []
        for cand in candidates:
            results.append({
                "candidate": cand.name,
                "party": cand.party,
                "votes": cand.votes,
                "alliance": get_alliance(cand.party, year, cand.name, const.constituency_name)
            })
            
        winner = results[0] if results else None
        runner_up = results[1] if len(results) > 1 else None
        margin = (winner["votes"] - runner_up["votes"]) if winner and runner_up else 0
        
        formatted_data.append({
            "name": const.constituency_name,
            "winner": winner["candidate"] if winner else "N/A",
            "party": winner["party"] if winner else "N/A",
            "alliance": winner["alliance"] if winner else "N/A",
            "votes": winner["votes"] if winner else 0,
            "margin": f"+{margin:,}",
            "results": results
        })
        
    return {"data": formatted_data}

@router.get("/constituencies/list")
def list_all_constituencies(session: Session = Depends(get_session)):
    # Get all unique constituency names and their latest entry
    # This query finds the latest record for each constituency name
    statement = select(Constituency).order_by(Constituency.constituency_name, Constituency.election_year.desc())
    all_records = session.exec(statement).all()
    
    unique_consts = {}
    for const in all_records:
        # Normalize name to avoid case duplicates
        norm_name = const.constituency_name.strip().upper()
        
        if norm_name not in unique_consts:
            # Get winner for this latest record
            cand_stmt = select(Candidate).where(Candidate.constituency_id == const.id).order_by(Candidate.votes.desc()).limit(1)
            winner = session.exec(cand_stmt).first()
            
            district = "Kannur" if norm_name == "DHARMADAM" else ("Kottayam" if norm_name == "PUTHUPPALLY" or norm_name == "POONJAR" else "Kerala")
            
            unique_consts[norm_name] = {
                "name": norm_name.title(), # Display in Title Case for better UX
                "district": district,
                "latest_year": const.election_year,
                "winner": winner.name if winner else "N/A",
                "party": winner.party if winner else "N/A",
                "alliance": get_alliance(winner.party, const.election_year, winner.name, norm_name) if winner else "N/A"
            }
            
    return {"data": sorted(list(unique_consts.values()), key=lambda x: x["name"])}

@router.get("/constituencies/search")
def search_constituencies(q: str, session: Session = Depends(get_session)):
    statement = select(Constituency.constituency_name).where(Constituency.constituency_name.ilike(f"%{q}%")).distinct()
    names = session.exec(statement).all()
    # Normalize result set
    unique_names = sorted(list(set(n.title() for n in names)))
    return {"data": unique_names}

@router.get("/constituencies/{name}/dashboard")
def get_constituency_dashboard(name: str, session: Session = Depends(get_session)):
    # 1. Fetch all records for this constituency name (case-insensitive)
    statement = select(Constituency).where(Constituency.constituency_name.ilike(name)).order_by(Constituency.election_year.desc())
    history_records = session.exec(statement).all()
    
    if not history_records:
        raise HTTPException(status_code=404, detail="Constituency not found")
    
    # 2. Build detailed history and timeline
    election_history = []
    alliance_timeline = []
    margin_trend = []
    
    total_wins = 0
    total_margin_perc = 0
    
    for const in history_records:
        candidates_stmt = select(Candidate).where(Candidate.constituency_id == const.id).order_by(Candidate.votes.desc())
        candidates = session.exec(candidates_stmt).all()
        
        if not candidates: continue
        
        winner = candidates[0]
        runner_up = candidates[1] if len(candidates) > 1 else None
        
        margin = winner.votes - (runner_up.votes if runner_up else 0)
        total_votes = sum(c.votes for c in candidates)
        margin_perc = (margin / total_votes * 100) if total_votes > 0 else 0
        
        alliance = get_alliance(winner.party, const.election_year, winner.name, const.constituency_name)
        
        election_history.append({
            "year": const.election_year,
            "winner": winner.name,
            "party": winner.party,
            "votes": winner.votes,
            "runner_up": runner_up.name if runner_up else "N/A",
            "margin": margin,
            "margin_perc": round(margin_perc, 2)
        })
        
        alliance_timeline.append({
            "year": const.election_year,
            "alliance": alliance
        })
        
        margin_trend.append({
            "year": const.election_year,
            "margin": margin,
            "margin_perc": round(margin_perc, 2)
        })

    # Summary and Stats
    latest = history_records[0]
    district = "Kannur" if latest.constituency_name == "Dharmadam" else ("Kottayam" if latest.constituency_name == "Puthuppally" else "Kerala")
    
    # Heuristic for Swing Propensity (Standard Deviation of margin percentage)
    if len(margin_trend) > 1:
        avg_margin = sum(m["margin_perc"] for m in margin_trend) / len(margin_trend)
        variance = sum((m["margin_perc"] - avg_margin)**2 for m in margin_trend) / len(margin_trend)
        swing_propensity = "High" if variance > 50 else ("Medium" if variance > 20 else "Low")
    else:
        swing_propensity = "Low"

    # Fallback for Electorate if missing (estimate based on votes polled and typical 75% turnout)
    votes_polled = latest.votes_polled or sum(c.votes for c in session.exec(select(Candidate).where(Candidate.constituency_id == latest.id)).all())
    electorate = latest.electorate or int(votes_polled / 0.76) # 76% is a very common turnout in Kerala
    turnout_perc = (votes_polled / electorate * 100) if electorate > 0 else 0

    return {
        "data": {
            "summary": {
                "name": latest.constituency_name,
                "district": district,
                "description": f"A historical constituency in {district} district, representing the political landscape of Kerala.",
                "total_electorate": electorate,
                "turnout": f"{round(turnout_perc, 2)}%"
            },
            "alliance_timeline": sorted(alliance_timeline, key=lambda x: x["year"]),
            "margin_trend": sorted(margin_trend, key=lambda x: x["year"]),
            "election_history": election_history,
            "stats": {
                "dominant_group": "Agrarian Workers" if district == "Kannur" else "Service Sector",
                "assemblies": len(history_records),
                "swing_propensity": f"{swing_propensity} ({round(variance, 1) if 'variance' in locals() else 0}%)"
            }
        }
    }
