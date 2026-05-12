# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException
# pyrefly: ignore [missing-import]
# pyrefly: ignore [missing-import]
from sqlmodel import Session, select, func
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import aliased
from core.database import get_session
from core.models import Election, Constituency, Candidate
from core.logic import get_alliance
from typing import List, Dict, Optional
import uuid

router = APIRouter(prefix="/api/v1/compare", tags=["compare"])

def get_year_metrics(year: int, session: Session):
    election = session.exec(select(Election).where(Election.year == year)).first()
    if not election: return None
        
    # 1. Base constituency data
    consts = session.exec(select(Constituency).where(Constituency.election_year == year)).all()
    const_ids = [c.id for c in consts]
    
    total_electorate = sum(c.electorate or 0 for c in consts)
    total_votes_polled = sum(c.votes_polled or 0 for c in consts)
    
    # Accurate vote count from candidates if missing in main table
    if total_votes_polled == 0:
        total_votes_polled = session.exec(select(func.sum(Candidate.votes)).where(Candidate.constituency_id.in_(const_ids))).one() or 0
    
    if total_electorate == 0: total_electorate = int(total_votes_polled / 0.75)

    # 2. Alliance, Seats & Margins (Optimized with one query)
    # We fetch winners and their respective runner-ups in one join
    Winner = aliased(Candidate)
    RunnerUp = aliased(Candidate)
    
    margins_stmt = (
        select(Winner, RunnerUp.votes.label("runner_votes"), Constituency.constituency_name)
        .join(Constituency, Winner.constituency_id == Constituency.id)
        .outerjoin(RunnerUp, (RunnerUp.constituency_id == Constituency.id) & (RunnerUp.rank == 2))
        .where(Constituency.election_year == year, Winner.rank == 1)
    )
    
    results = session.exec(margins_stmt).all()
    
    ldf_seats, udf_seats, nda_seats, ind_seats = 0, 0, 0, 0
    total_margin = 0
    women_elected = 0
    
    for winner, runner_votes, cname in results:
        alliance = get_alliance(winner.party, year, winner.name, cname)
        if alliance == "LDF": ldf_seats += 1
        elif alliance == "UDF": udf_seats += 1
        elif alliance == "NDA": nda_seats += 1
        
        if winner.party.upper() == "IND": ind_seats += 1
        if winner.sex == 'F': women_elected += 1
        
        if runner_votes:
            total_margin += (winner.votes - runner_votes)

    avg_margin = total_margin / len(results) if results else 0

    # 3. Candidate Stats
    total_cands = session.exec(select(func.count(Candidate.id)).where(Candidate.constituency_id.in_(const_ids))).one()
    women_cands = session.exec(select(func.count(Candidate.id)).where(Candidate.constituency_id.in_(const_ids), Candidate.sex == 'F')).one()

    # 4. NOTA & Deposits (Optimized)
    total_nota = sum(c.nota_votes or 0 for c in consts)
    
    # Deposit forfeited: votes < 1/6 of total valid votes
    # Use SQL for this check
    forfeited_stmt = (
        select(func.count(Candidate.id))
        .join(Constituency, Candidate.constituency_id == Constituency.id)
        .where(
            Constituency.election_year == year,
            Candidate.votes < (func.coalesce(Constituency.votes_polled, Candidate.votes * 1.3) / 6)
        )
    )
    forfeited = session.exec(forfeited_stmt).one()

    return {
        "year": year,
        "turnout": round((total_votes_polled / total_electorate * 100), 2) if total_electorate > 0 else 0,
        "ldf_seats": ldf_seats,
        "udf_seats": udf_seats,
        "nda_seats": nda_seats,
        "ind_seats": ind_seats,
        "total_electorate": total_electorate,
        "total_votes": total_votes_polled,
        "total_candidates": total_cands,
        "avg_margin": int(avg_margin),
        "women_perc": round((women_cands / total_cands * 100), 2) if total_cands > 0 else 0,
        "women_elected": women_elected,
        "nota_total": total_nota,
        "forfeited": forfeited
    }


@router.get("/years")
def compare_years(y1: int, y2: int, session: Session = Depends(get_session)):
    m1 = get_year_metrics(y1, session)
    m2 = get_year_metrics(y2, session)
    if not m1 or not m2: raise HTTPException(status_code=404, detail="Year not found")
    
    # Calculate switched seats
    w1 = session.exec(select(Candidate.party, Constituency.constituency_name).join(Constituency).where(Constituency.election_year == y1, Candidate.rank == 1)).all()
    w2 = session.exec(select(Candidate.party, Constituency.constituency_name).join(Constituency).where(Constituency.election_year == y2, Candidate.rank == 1)).all()
    ma = {name.upper(): party for party, name in w1}
    mb = {name.upper(): party for party, name in w2}
    switched = sum(1 for name, pb in mb.items() if ma.get(name) and ma.get(name) != pb)

    return {"baseline": m1, "comparison": m2, "switched_seats": switched}

@router.get("/constituencies")
def compare_constituencies(c1: str, c2: str, session: Session = Depends(get_session)):
    def get_const_analytics(name):
        recs = session.exec(select(Constituency).where(Constituency.constituency_name.ilike(name)).order_by(Constituency.election_year)).all()
        if not recs: return None
        
        ids = [r.id for r in recs]
        # Fetch all candidates for these IDs in one go
        cands = session.exec(select(Candidate).where(Candidate.constituency_id.in_(ids))).all()
        
        # Pre-process winners and runner-ups for performance
        winners_map = {c.constituency_id: c for c in cands if c.rank == 1}
        runners_map = {c.constituency_id: c for c in cands if c.rank == 2}
        
        margins = []
        for cid, winner in winners_map.items():
            runner = runners_map.get(cid)
            if runner: margins.append(winner.votes - runner.votes)
        
        # Turnout & Electorate
        latest = recs[-1]
        earliest = recs[0]
        turnouts = [(r.votes_polled / r.electorate * 100) for r in recs if r.electorate and r.votes_polled]
        
        # Flipping detect
        flips = 0
        prev_alliance = None
        for r in recs:
            w = winners_map.get(r.id)
            if w:
                curr_alliance = get_alliance(w.party, r.election_year, w.name, r.constituency_name)
                if prev_alliance and curr_alliance != prev_alliance: flips += 1
                prev_alliance = curr_alliance

        return {
            "name": name,
            "win_count": len(winners_map),
            "avg_margin": int(sum(margins)/len(margins)) if margins else 0,
            "flips": flips,
            "highest_turnout": round(max(turnouts), 2) if turnouts else 0,
            "lowest_turnout": round(min(turnouts), 2) if turnouts else 0,
            "current_electorate": latest.electorate,
            "electorate_growth": (latest.electorate or 0) - (earliest.electorate or 0),
            "total_candidates": len(cands),
            "avg_candidates": round(len(cands) / len(recs), 1) if recs else 0,
            "closest_race": min(margins) if margins else 0,
            "biggest_landslide": max(margins) if margins else 0,
            "women_contested": len([c for c in cands if c.sex == 'F']),
            "women_won": len([c for c in winners_map.values() if c.sex == 'F']),
            "nota_avg": round(sum(r.nota_votes or 0 for r in recs[-2:]) / sum(r.votes_polled or 1 for r in recs[-2:]) * 100, 2)
        }

    d1 = get_const_analytics(c1)
    d2 = get_const_analytics(c2)
    if not d1 or not d2: raise HTTPException(status_code=404, detail="Constituency not found")
    return {"baseline": d1, "comparison": d2}

@router.get("/candidates")
def compare_candidates(name1: str, name2: str, session: Session = Depends(get_session)):
    def get_cand_career(name):
        # Explicit join for safety
        results = session.exec(
            select(Candidate, Constituency.constituency_name, Election.year)
            .join(Constituency, Candidate.constituency_id == Constituency.id)
            .join(Election, Constituency.election_year == Election.year)
            .where(Candidate.name.ilike(f"%{name}%"))
            .order_by(Election.year)
        ).all()
        
        if not results: return None
        
        rows = [r[0] for r in results]
        const_ids = [r.constituency_id for r in rows]
        
        # Batch fetch all potential winners/runners for these seats to calculate margins efficiently
        peer_cands = session.exec(select(Candidate).where(Candidate.constituency_id.in_(const_ids), Candidate.rank.in_([1, 2]))).all()
        
        # Map peers
        peer_winners = {c.constituency_id: c for c in peer_cands if c.rank == 1}
        peer_runners = {c.constituency_id: c for c in peer_cands if c.rank == 2}
        
        margins = []
        for r in rows:
            if r.rank == 1: # Win margin
                runner = peer_runners.get(r.constituency_id)
                if runner: margins.append(r.votes - runner.votes)
            else: # Loss margin
                winner = peer_winners.get(r.constituency_id)
                if winner: margins.append(winner.votes - r.votes)

        best_vote = max(rows, key=lambda x: x.votes)
        best_share = max(rows, key=lambda x: x.vote_percentage or 0)
        
        return {
            "name": rows[0].name,
            "contested": len(rows),
            "wins": len([r for r in rows if r.rank == 1]),
            "win_rate": round(len([r for r in rows if r.rank == 1])/len(rows)*100, 1),
            "total_votes": sum(r.votes for r in rows),
            "best_votes": best_vote.votes,
            "best_share": best_share.vote_percentage,
            "avg_share": round(sum(r.vote_percentage or 0 for r in rows)/len(rows), 2),
            "seats": list(set(r[1] for r in results)),
            "parties": list(set(r.party for r in rows)),
            "first_year": results[0][2],
            "last_year": results[-1][2],
            "span": results[-1][2] - results[0][2],
            "max_margin": max(margins) if margins else 0,
            "min_margin": min(margins) if margins else 0
        }

    b1 = get_cand_career(name1)
    b2 = get_cand_career(name2)
    if not b1 or not b2: raise HTTPException(status_code=404, detail="Candidate not found")
    return {"baseline": b1, "comparison": b2}
