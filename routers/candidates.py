# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends
from collections import Counter
# pyrefly: ignore [missing-import]
from sqlmodel import Session, select
from core.database import get_session
from core.models import Candidate, Constituency
from core.logic import get_alliance

router = APIRouter(prefix="/api/v1/candidates", tags=["candidates"])

@router.get("/search")
def search_candidates(q: str, session: Session = Depends(get_session)):
    # Fetch candidates with similar names
    statement = (
        select(Candidate.name, Candidate.party)
        .where(Candidate.name.ilike(f"%{q}%"))
        .limit(100)
    )
    results = session.exec(statement).all()
    
    # Intelligent Deduplication Algorithm
    candidates_group = {}
    for name, party in results:
        # Normalize: lowercase, remove dots/special chars, strip whitespace
        norm = name.lower().replace(".", "").strip()
        
        if norm not in candidates_group:
            candidates_group[norm] = {
                "original_names": Counter(),
                "parties": Counter()
            }
        
        candidates_group[norm]["original_names"][name] += 1
        candidates_group[norm]["parties"][party] += 1
    
    data = []
    for norm, info in candidates_group.items():
        # Pick the most common casing for display
        display_name = info["original_names"].most_common(1)[0][0]
        # Pick the most common party
        display_party = info["parties"].most_common(1)[0][0]
        
        data.append({
            "name": display_name,
            "party": display_party
        })
        
    return {"data": data[:15]}

@router.get("/{candidate_name}/timeline")
def get_candidate_timeline(candidate_name: str, session: Session = Depends(get_session)):
    # Normalize input for search
    search_term = candidate_name.lower().replace(".", "").strip()
    
    # Fetch all candidates that might match
    # We use ILIKE to catch different casings in one go
    statement = (
        select(Candidate, Constituency)
        .join(Constituency, Candidate.constituency_id == Constituency.id)
        .where(Candidate.name.ilike(f"{candidate_name}%"))
        .order_by(Constituency.election_year.desc())
    )
    results = session.exec(statement).all()
    
    timeline = []
    wins = 0
    total_votes = 0
    
    seen_years = set()
    for cand, const in results:
        # Secondary filter in Python for strict normalization matching
        # This handles cases like "Oommen Chandy" matching "OOMMEN CHANDY"
        if cand.name.lower().replace(".", "").strip() != search_term:
            continue
            
        # Avoid duplicate records for the same year if data is messy
        if const.election_year in seen_years:
            continue
        seen_years.add(const.election_year)
        
        is_win = (cand.rank == 1)
        if is_win: wins += 1
        total_votes += (cand.votes or 0)
        
        timeline.append({
            "year": const.election_year,
            "constituency": const.constituency_name,
            "party": cand.party,
            "votes": cand.votes,
            "rank": cand.rank,
            "vote_percentage": cand.vote_percentage,
            "alliance": get_alliance(cand.party, const.election_year, cand.name, const.constituency_name)
        })
        # Calculate career stats in backend for frontend efficiency
    count = len(timeline)
    summary = {
        "elections": count,
        "wins": wins,
        "win_rate": f"{round((wins/count)*100, 1)}%" if count > 0 else "0%",
        "total_votes": total_votes,
        "status": "Active" if timeline and timeline[0]["year"] >= 2021 else "Retired"
    }
    
    return {
        "data": timeline, 
        "summary": summary
    }

@router.get("/featured")
def get_featured_candidates(session: Session = Depends(get_session)):
    # Return a unique set of prominent winners
    statement = (
        select(Candidate.name, Candidate.party)
        .where(Candidate.rank == 1)
        .limit(100)
    )
    results = session.exec(statement).all()
    
    # Simple deduplication by normalized name
    candidates_group = {}
    for name, party in results:
        norm = name.lower().replace(".", "").strip()
        if norm not in candidates_group:
            candidates_group[norm] = {"name": name, "party": party}
            
    data = list(candidates_group.values())[:10]
    return {"data": data}
