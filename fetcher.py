import requests, time, json, csv
from urllib.parse import quote

API_KEY = "RGAPI-c65c5fef-59e8-44dd-8aca-9094e92c8054"
HEADERS = {"X-Riot-Token": API_KEY}

PLATFORM = "na1"
REGION = "americas"
QUEUE = "RANKED_SOLO_5x5"

# File to track processed match IDs
PROCESSED_MATCHES_FILE = "processed_matches.json"

# Rate limiting - more conservative
REQUEST_DELAY = 2  # 2 seconds between requests
BATCH_DELAY = 120  # 2 minutes between batches

def get_master_entries():
    url = f"https://{PLATFORM}.api.riotgames.com/lol/league/v4/masterleagues/by-queue/{QUEUE}"
    time.sleep(REQUEST_DELAY)
    return requests.get(url, headers=HEADERS).json().get("entries", [])

def get_puuid(summoner_id):
    url = f"https://{PLATFORM}.api.riotgames.com/lol/summoner/v4/summoners/{summoner_id}"
    time.sleep(REQUEST_DELAY)
    return requests.get(url, headers=HEADERS).json().get("puuid")

def get_match_ids(puuid, count=10):
    url = f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count={count}"
    time.sleep(REQUEST_DELAY)
    return requests.get(url, headers=HEADERS).json()

def get_match_data(match_id):
    url = f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    time.sleep(REQUEST_DELAY)
    return requests.get(url, headers=HEADERS).json()

def load_processed_matches():
    try:
        with open(PROCESSED_MATCHES_FILE, "r") as f:
            return set(json.load(f))
    except:
        return set()

def save_processed_matches(match_ids):
    with open(PROCESSED_MATCHES_FILE, "w") as f:
        json.dump(list(match_ids), f)

def save_match_data(match):
    match_id = match["metadata"]["matchId"]
    with open(f"matches/{match_id}.json", "w") as f:
        json.dump(match, f, indent=2)

def extract_player_stats(match_json):
    fields = [
        #player_info
        "riotIdGameName", "championName", "teamPosition", "win",
        "kills", "deaths", "assists", "soloKills", "firstBloodKill", "consumablesPurchased",
        "damageDealtToObjectives", "damageSelfMitigated", "totalDamageTaken",
        "totalDamageDealtToChampions", "champExperience", "goldEarned", "goldSpent",
        
        #vision
        "visionScore", "sightWardsBoughtInGame", "wardsPlaced", "wardsKilled", "detectorWardsPlaced",

        #creep score
        "neutralMinionsKilled", "totalMinionsKilled", "totalAllyJungleMinionsKilled", "totalEnemyJungleMinionsKilled",

        #player_stats
        "spell1Casts", "spell2Casts", "spell3Casts", "spell4Casts",
        "item0", "item1", "item2", "item3", "item4", "item5", "item6", "itemsPurchased",
        "summoner1Id", "summoner1Casts", "summoner2Id", "summoner2Casts",

        #player communication
        "allInPings", "assistMePings", "commandPings", "enemyMissingPings", "enemyVisionPings",
        "holdPings", "getBackPings", "needVisionPings", "onMyWayPings", "pushPings", "visionClearedPings",

        #objectives
        "objectivesStolen", "firstTowerKill", "firstTowerAssist", "turretKills", "turretTakedowns"
    ]
    
    # Calculate team-level stats from teams array
    team_stats = {}
    for team in match_json["info"]["teams"]:
        team_id = team["teamId"]
        objectives = team.get("objectives", {})
        feats = team.get("feats", {})
        team_stats[team_id] = {
            "baronFirst": objectives.get("baron", {}).get("first", False),
            "baronKills": objectives.get("baron", {}).get("kills", 0),
            "dragonFirst": objectives.get("dragon", {}).get("first", False),
            "dragonKills": objectives.get("dragon", {}).get("kills", 0),
            "inhibitorFirst": objectives.get("inhibitor", {}).get("first", False),
            "inhibitorKills": objectives.get("inhibitor", {}).get("kills", 0),
            "riftHeraldKills": objectives.get("riftHerald", {}).get("kills", 0),
            "championKills": objectives.get("champion", {}).get("kills", 0),
            "atakhanKills": objectives.get("atakhan", {}).get("kills", 0),
            "epicMonsterKill": feats.get("EPIC_MONSTER_KILL", {}).get("featState", 0),
            "firstBlood": feats.get("FIRST_BLOOD", {}).get("featState", 0),
            "firstTurret": feats.get("FIRST_TURRET", {}).get("featState", 0),
        }
    
    return [
        {
            # Extract match-level and player-specific fields in correct order
            "matchId": match_json["metadata"]["matchId"],
            "teamId": player["teamId"],
            "gameDuration": match_json["info"]["gameDuration"],
            "participantId": player["participantId"],
            **{field: player.get(field, None) for field in fields},
            # Apply team-level stats to all players on the team
            "baronFirst": team_stats[player["teamId"]]["baronFirst"],
            "baronKills": team_stats[player["teamId"]]["baronKills"],
            "dragonFirst": team_stats[player["teamId"]]["dragonFirst"],
            "dragonKills": team_stats[player["teamId"]]["dragonKills"],
            "inhibitorFirst": team_stats[player["teamId"]]["inhibitorFirst"],
            "inhibitorKills": team_stats[player["teamId"]]["inhibitorKills"],
            "riftHeraldKills": team_stats[player["teamId"]]["riftHeraldKills"],
            "championKills": team_stats[player["teamId"]]["championKills"],
            "atakhanKills": team_stats[player["teamId"]]["atakhanKills"],
            "epicMonsterKill": team_stats[player["teamId"]]["epicMonsterKill"],
            "firstBlood": team_stats[player["teamId"]]["firstBlood"],
            "firstTurret": team_stats[player["teamId"]]["firstTurret"],
            # Extract nested challenge fields
            "soloKills": player.get("challenges", {}).get("soloKills", None),
            "damagePerMinute": player.get("challenges", {}).get("damagePerMinute", None),
            "visionScoreAdvantageLaneOpponent": player.get("challenges", {}).get("visionScoreAdvantageLaneOpponent", None),
            "visionScorePerMinute": player.get("challenges", {}).get("visionScorePerMinute", None),
            "stealthWardsPlaced": player.get("challenges", {}).get("stealthWardsPlaced", None),
            "laneMinionsFirst10Minutes": player.get("challenges", {}).get("laneMinionsFirst10Minutes", None),
            "jungleCsBefore10Minutes": player.get("challenges", {}).get("jungleCsBefore10Minutes", None),
            "firstTurretKilledTime": player.get("challenges", {}).get("firstTurretKilledTime", None),
            "turretPlatesTaken": player.get("challenges", {}).get("turretPlatesTaken", None),
            "maxLevelLeadLaneOpponent": player.get("challenges", {}).get("maxLevelLeadLaneOpponent", None),
            "maxCsAdvantageOnLaneOpponent": player.get("challenges", {}).get("maxCsAdvantageOnLaneOpponent", None),
            "maxKillDeficit": player.get("challenges", {}).get("maxKillDeficit", None),
        }
        for player in match_json["info"]["participants"]
    ]

def save_player_stats_csv(player_stats, filename="player_stats.csv"):
    """Save player stats to CSV file"""
    if not player_stats:
        return
    
    # Define the fields we want in the CSV
    fields = [
        "matchId", "teamId", "gameDuration", "participantId", "riotIdGameName", "championName", "teamPosition", "win",
        "kills", "deaths", "assists", "soloKills", "firstBloodKill", "consumablesPurchased",
        "damageDealtToObjectives", "damageSelfMitigated", "totalDamageTaken",
        "totalDamageDealtToChampions", "champExperience", "goldEarned", "goldSpent",
        "visionScore", "sightWardsBoughtInGame", "wardsPlaced", "wardsKilled", "detectorWardsPlaced",
        "neutralMinionsKilled", "totalMinionsKilled", "totalAllyJungleMinionsKilled", "totalEnemyJungleMinionsKilled",
        "spell1Casts", "spell2Casts", "spell3Casts", "spell4Casts",
        "item0", "item1", "item2", "item3", "item4", "item5", "item6", "itemsPurchased",
        "summoner1Id", "summoner1Casts", "summoner2Id", "summoner2Casts",
        "allInPings", "assistMePings", "commandPings", "enemyMissingPings", "enemyVisionPings",
        "holdPings", "getBackPings", "needVisionPings", "onMyWayPings", "pushPings", "visionClearedPings",
        "objectivesStolen", "firstTowerKill", "firstTowerAssist", "turretKills", "turretTakedowns",
        "baronFirst", "baronKills", "dragonFirst", "dragonKills", "inhibitorFirst", "inhibitorKills",
        "riftHeraldKills", "championKills", "atakhanFirst", "atakhanKills",
        "epicMonsterKill", "firstBlood", "firstTurret",
        "damagePerMinute", "visionScoreAdvantageLaneOpponent", "visionScorePerMinute", "stealthWardsPlaced",
        "laneMinionsFirst10Minutes", "jungleCsBefore10Minutes",
        "firstTurretKilledTime", "turretPlatesTaken",
        "maxLevelLeadLaneOpponent", "maxCsAdvantageOnLaneOpponent", "maxKillDeficit"
    ]
    
    # Check if file exists to determine if we need to write header
    file_exists = False
    try:
        with open(filename, 'r') as f:
            file_exists = True
    except FileNotFoundError:
        pass
    
    with open(filename, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if not file_exists:
            writer.writeheader()
        writer.writerows(player_stats)

def main_loop():
    processed = load_processed_matches()
    print("Starting data collection with conservative rate limiting...")
    
    try:
        entries = get_master_entries()
        print(f"Fetched {len(entries)} players")

        # Process only the first player for testing
        entry = entries[0]
        print(f"Processing player: {entry.get('riotIdGameName', 'Unknown')}")
        
        puuid = get_puuid(entry["summonerId"])
        if not puuid:
            print(f"Could not get PUUID for {entry.get('riotIdGameName', 'Unknown')}")
            return

        match_ids = get_match_ids(puuid, count=1)  # Only get 1 match
        for match_id in match_ids:
            if match_id in processed:
                print(f"Match {match_id} already processed, skipping...")
                continue

            try:
                print(f"Fetching match {match_id}...")
                match_data = get_match_data(match_id)
                # save_match_data(match_data)  # Removed - no longer saving full JSON files

                # Extract and save player stats to CSV
                player_stats = extract_player_stats(match_data)
                save_player_stats_csv(player_stats)
                
                # Print summary
                print(f"Extracted stats for {len(player_stats)} players:")
                for stat in player_stats:
                    print(f"  {stat['riotIdGameName']}: {stat['championName']} - {stat['kills']}/{stat['deaths']}/{stat['assists']}")

                processed.add(match_id)
                print("Test completed successfully!")
                return  # Exit after one match
                
            except Exception as e:
                print(f"Error fetching match {match_id}: {e}")
                time.sleep(10)  # Longer delay on error

    except Exception as e:
        print(f"Error in main loop: {e}")
        time.sleep(30)



