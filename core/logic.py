def get_alliance(party: str | None, year: int = 2021, candidate_name: str | None = None, area_name: str | None = None) -> str:
    if not party: return "OTHERS"
    p = party.upper().strip()
    
    # 1. 2026 UDF-backed Independents (Special Case)
    if year == 2026 and (p == "IND" or p == "INDEPENDENT"):
        udf_ind_candidates = ["GSUDHAKARAN", "TKGOVINDANMASTER", "VKUNHIKRISHNAN", "PVANVAR"]
        udf_ind_areas = ["AMBALAPPUZHA", "TALIPARAMBA", "PAYYANUR", "BEYPORE"]
        c_norm = candidate_name.upper().replace(".", "").replace(" ", "") if candidate_name else ""
        if (c_norm and any(name in c_norm for name in udf_ind_candidates)) or (area_name and area_name.upper() in udf_ind_areas):
            return "UDF"

    # 2. Kerala Congress (M) - The major shifter
    if "KERALA CONGRESS (M)" in p or "KC(M)" in p or p == "KCM":
        return "LDF" if year >= 2021 else "UDF"

    # LDF Parties (Broad matching for robustness)
    ldf_exact = [
        "CPI(M)", "CPIM", "CPM", "COMMUNIST PARTY OF INDIA (MARXIST)",
        "CPI", "COMMUNIST PARTY OF INDIA", "COMMUNIST PARTY OF INDIA(MARXIST)",
        "CPI (M)", "CPI ( MARXIST )",
        "NCP", "NATIONALIST CONGRESS PARTY", "N.C.P.",
        "JD(S)", "JDS", "JANATA DAL (SECULAR)", "JANATHA DAL (SECULAR)",
        "LJD", "LOKTANTRIK JANATA DAL", "LOK TANTRIC JANATA DAL",
        "INL", "INDIAN NATIONAL LEAGUE",
        "JKC", "JANADHIPATHYA KERALA CONGRESS",
        "NSC", "NATIONAL SECULAR CONFERENCE",
        "RJD", "RASHTRIYA JANATA DAL",
        "KC(B)", "KERALA CONGRESS (B)", "KCB",
        "RSPL", "RSP(LENO)", "RSP(L)",
        "LDF", "C6", "LDF-IND"
    ]
    if p in ldf_exact or p.startswith("CPI") or p.startswith("CPM") or "COMMUNIST" in p:
        return "LDF"

    # UDF Parties (Broad matching for robustness)
    udf_exact = [
        "INC", "INDIAN NATIONAL CONGRESS", "INC(I)", "CONGRESS",
        "IUML", "INDIAN UNION MUSLIM LEAGUE", "MUSLIM LEAGUE", "I.U.M.L.", "MUL",
        "KEC", "KERALA CONGRESS", "KERALA CONGRESS (JOSEPH)", "KC(J)", "KEC-J", "KC-J",
        "KC(JACOB)", "KERALA CONGRESS (JACOB)", "KCJ", "K.C.J.",
        "RSP", "REVOLUTIONARY SOCIALIST PARTY", "R.S.P.",
        "CMP", "COMMUNIST MARXIST PARTY", "CMP(J)",
        "RMPI", "REVOLUTIONARY MARXIST PARTY OF INDIA",
        "NCK", "NATIONALIST CONGRESS KERALA",
        "UDF", "UDF-IND"
    ]
    if p in udf_exact or p.startswith("INC") or p.startswith("IUML") or "MUSLIM LEAGUE" in p:
        return "UDF"

    # NDA Parties
    if p in ["BJP", "BHARATIYA JANATA PARTY", "BDJS", "AIADMK", "NDA"] or p.startswith("BJP"):
        return "NDA"
                
    return "OTHERS"
