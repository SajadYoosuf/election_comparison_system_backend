
from sqlmodel import Session, create_engine, select, func
from core.models import Election, Constituency, Candidate
from core.logic import get_alliance
import os

from core.database import engine

def check_2021_results():
    with Session(engine) as session:
        year = 2021
        constituencies = session.exec(select(Constituency).where(Constituency.election_year == year)).all()
        print(f"Total Constituencies for {year}: {len(constituencies)}")
        
        alliance_counts = {"LDF": 0, "UDF": 0, "NDA": 0, "OTHERS": 0}
        
        for const in constituencies:
            # Get winner for this constituency
            winner = session.exec(
                select(Candidate)
                .where(Candidate.constituency_id == const.id)
                .order_by(Candidate.votes.desc())
            ).first()
            
            if winner:
                alliance = get_alliance(winner.party, year, winner.name, const.constituency_name)
                alliance_counts[alliance] += 1
            else:
                print(f"No candidates for {const.constituency_name} ({year})")
                
        print(f"Alliance Counts for {year}: {alliance_counts}")
        winning_alliance = max(alliance_counts, key=alliance_counts.get)
        print(f"Winning Alliance for {year}: {winning_alliance}")

if __name__ == "__main__":
    check_2021_results()
