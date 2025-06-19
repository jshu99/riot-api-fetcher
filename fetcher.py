import requests, time, json, csv
from urllib.parse import quote

API_KEY = "RGAPI-331685ef-bd1c-44a2-80b7-5a1848bef044"
HEADERS = {"X-Riot-Token": API_KEY}

PLATFORM = "na1"
REGION = "americas"
QUEUE = "RANKED_SOLO_5x5"

# File to track processed match IDs
PROCESSED_MATCHES_FILE = "processed_matches_new.json"
PLAYER_MATCH_RANGES_FILE = "player_match_ranges_new.json"  # Track which match ranges we've processed per player

# Rate limiting - optimized for Riot's API limits
REQUEST_DELAY = 0.5  # 100ms between requests (10 requests per second)
BATCH_DELAY = 120  # 30 seconds between batches
PLAYERS_PER_BATCH = 50  # Process 50 players per batch
MATCHES_PER_PLAYER = 10  # Get 10 matches per player

def get_master_entries():
    url = f"https://{PLATFORM}.api.riotgames.com/lol/league/v4/masterleagues/by-queue/{QUEUE}"
    time.sleep(REQUEST_DELAY)
    response = requests.get(url, headers=HEADERS)
    data = response.json()
    
    # Check for rate limit or other errors
    if 'status' in data:
        print(f"API Error: {data['status']}")
        return []
    
    return data.get("entries", [])

def get_puuid(summoner_id):
    url = f"https://{PLATFORM}.api.riotgames.com/lol/summoner/v4/summoners/{summoner_id}"
    time.sleep(REQUEST_DELAY)
    response = requests.get(url, headers=HEADERS)
    data = response.json()
    
    # Check for rate limit or other errors
    if 'status' in data:
        print(f"API Error getting PUUID: {data['status']}")
        return None
    
    return data.get("puuid")

def get_match_ids(puuid, count=10, start=0):
    # Only get ranked solo queue matches (queue ID 420)
    url = f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start={start}&count={count}&queue=420"
    time.sleep(REQUEST_DELAY)
    response = requests.get(url, headers=HEADERS)
    data = response.json()
    
    # Check for rate limit or other errors
    if 'status' in data:
        print(f"API Error getting match IDs: {data['status']}")
        return []
    
    return data

def get_match_data(match_id):
    url = f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    time.sleep(REQUEST_DELAY)
    response = requests.get(url, headers=HEADERS)
    data = response.json()
    
    # Check for rate limit or other errors
    if 'status' in data:
        print(f"API Error getting match data: {data['status']}")
        return None
    
    return data

def load_processed_matches():
    try:
        with open(PROCESSED_MATCHES_FILE, "r") as f:
            return set(json.load(f))
    except:
        return set()

def load_player_match_ranges():
    try:
        with open(PLAYER_MATCH_RANGES_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_processed_matches(match_ids):
    with open(PROCESSED_MATCHES_FILE, "w") as f:
        json.dump(list(match_ids), f)

def save_player_match_ranges(player_ranges):
    with open(PLAYER_MATCH_RANGES_FILE, "w") as f:
        json.dump(player_ranges, f)

def save_match_data(match):
    match_id = match["metadata"]["matchId"]
    with open(f"matches/{match_id}.json", "w") as f:
        json.dump(match, f, indent=2)

def extract_player_stats(match_json):
    fields = [
        #player_info
        "puuid","riotIdGameName", "summonerLevel", "championName", "teamPosition", "role", "win", 'gameEndedInEarlySurrender', 'gameEndedInSurrender',
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
        "basicPings", "allInPings", "assistMePings", "commandPings", "enemyMissingPings", "enemyVisionPings",
        "holdPings", "getBackPings", "needVisionPings", "onMyWayPings", "pushPings", "visionClearedPings",
        

        #objectives
        "objectivesStolen", "firstTowerKill", "firstTowerAssist", "turretKills", "turretTakedowns", "dragonKills"
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
            "gameMode": match_json["info"].get("gameMode", None),
            "gameVersion": match_json["info"].get("gameVersion", None),
            "mapId": match_json["info"].get("mapId", None),
            "gameEndedInEarlySurrender": match_json["info"].get("gameEndedInEarlySurrender", None),
            "gameEndedInSurrender": match_json["info"].get("gameEndedInSurrender", None),
            "participantId": player["participantId"],
            **{field: player.get(field, None) for field in fields},
            # Apply team-level stats to all players on the team
            "baronFirst": team_stats[player["teamId"]]["baronFirst"],
            "baronKills": team_stats[player["teamId"]]["baronKills"],
            "dragonFirst": team_stats[player["teamId"]]["dragonFirst"],
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
            "controlWardsPlaced": player.get("challenges", {}).get("controlWardsPlaced", None),
            "laneMinionsFirst10Minutes": player.get("challenges", {}).get("laneMinionsFirst10Minutes", None),
            "jungleCsBefore10Minutes": player.get("challenges", {}).get("jungleCsBefore10Minutes", None),
            "firstTurretKilledTime": player.get("challenges", {}).get("firstTurretKilledTime", None),
            "turretPlatesTaken": player.get("challenges", {}).get("turretPlatesTaken", None),
            "maxLevelLeadLaneOpponent": player.get("challenges", {}).get("maxLevelLeadLaneOpponent", None),
            "maxCsAdvantageOnLaneOpponent": player.get("challenges", {}).get("maxCsAdvantageOnLaneOpponent", None),
            "maxKillDeficit": player.get("challenges", {}).get("maxKillDeficit", None),
            "fistBumpParticipation": player.get("challenges", {}).get("fistBumpParticipation", None),
            "teamElderDragonKills": player.get("challenges", {}).get("teamElderDragonKills", None),
            "abilityUses": player.get("challenges", {}).get("abilityUses", None),
            "hadOpenNexus": player.get("challenges", {}).get("hadOpenNexus", None),
            "wardTakedownsBefore20M": player.get("challenges", {}).get("wardTakedownsBefore20M", None),
        }
        for player in match_json["info"]["participants"]
    ]

def save_player_stats_csv(player_stats, filename="player_stats_new.csv"):
    """Save player stats to CSV file"""
    if not player_stats:
        return
    
    # Define the fields we want in the CSV
    fields = [
        "matchId", "gameDuration", "gameMode", "gameVersion", "mapId", "gameEndedInEarlySurrender", "gameEndedInSurrender", "teamId","win", "championKills", "participantId", 
        "puuid", "riotIdGameName", "summonerLevel", "championName", "role", "teamPosition", "champExperience", "kills", "deaths", "assists", "soloKills", 
        "firstBloodKill", "consumablesPurchased", "damageDealtToObjectives", "damageSelfMitigated", "totalDamageTaken",
        "firstTowerKill", "firstTowerAssist", "turretKills", "turretTakedowns", "turretPlatesTaken", "firstTurretKilledTime",
        "totalDamageDealtToChampions", "damagePerMinute", "goldEarned", "goldSpent",
        "visionScore", "sightWardsBoughtInGame", "wardsPlaced","stealthWardsPlaced", "controlWardsPlaced", "wardsKilled", "detectorWardsPlaced", 
        "visionScorePerMinute", "wardTakedownsBefore20M", "visionScoreAdvantageLaneOpponent",
        "neutralMinionsKilled", "totalMinionsKilled", "totalAllyJungleMinionsKilled", "totalEnemyJungleMinionsKilled", 
        "laneMinionsFirst10Minutes", "jungleCsBefore10Minutes", "maxLevelLeadLaneOpponent", "maxCsAdvantageOnLaneOpponent",
        "spell1Casts", "spell2Casts", "spell3Casts", "spell4Casts", "abilityUses", "summoner1Id", "summoner1Casts", "summoner2Id", "summoner2Casts", 
        "item0", "item1", "item2", "item3", "item4", "item5", "item6", "itemsPurchased",
        "basicPings", "allInPings", "assistMePings", "commandPings", "enemyMissingPings", "enemyVisionPings",
        "holdPings", "getBackPings", "needVisionPings", "onMyWayPings", "pushPings", "visionClearedPings", "fistBumpParticipation",
        "objectivesStolen", "baronFirst", "inhibitorFirst","dragonFirst", "baronKills", "inhibitorKills", "dragonKills",
        "riftHeraldKills", "atakhanKills", "epicMonsterKill", "firstBlood", "firstTurret", "maxKillDeficit", "teamElderDragonKills","hadOpenNexus"
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
    player_ranges = load_player_match_ranges()
    print("Starting data collection with optimized rate limiting...")
    
    while True:
        try:
            entries = get_master_entries()
            print(f"Fetched {len(entries)} players")

            # Process first 50 players to optimize rate limits
            for i, entry in enumerate(entries[:PLAYERS_PER_BATCH]):
                player_id = entry["summonerId"]
                print(f"Processing player {i+1}/{PLAYERS_PER_BATCH}: {entry.get('riotIdGameName', 'Unknown')}")
                
                puuid = get_puuid(player_id)
                if not puuid:
                    print(f"Could not get PUUID for {entry.get('riotIdGameName', 'Unknown')}")
                    continue

                # Get the next batch of matches for this player
                start_index = player_ranges.get(player_id, 0)
                match_ids = get_match_ids(puuid, count=MATCHES_PER_PLAYER, start=start_index)
                
                if not match_ids:
                    print(f"No more matches found for player {entry.get('riotIdGameName', 'Unknown')}")
                    continue
                
                new_matches_found = 0
                for match_id in match_ids:
                    if match_id in processed:
                        print(f"Match {match_id} already processed, skipping...")
                        continue

                    try:
                        print(f"Fetching match {match_id}...")
                        match_data = get_match_data(match_id)
                        
                        # Check if we got valid match data
                        if match_data is None:
                            print(f"Failed to get match data for {match_id}, skipping...")
                            continue
                        
                        # Extract and save player stats to CSV
                        player_stats = extract_player_stats(match_data)
                        save_player_stats_csv(player_stats)
                        
                        # Print summary
                        print(f"Extracted stats for {len(player_stats)} players:")
                        for stat in player_stats:
                            print(f"  {stat['riotIdGameName']}: {stat['championName']} - {stat['kills']}/{stat['deaths']}/{stat['assists']}")

                        processed.add(match_id)
                        new_matches_found += 1
                        time.sleep(REQUEST_DELAY)  # Rate limit between matches
                        
                    except Exception as e:
                        print(f"Error processing match {match_id}: {e}")
                        time.sleep(10)  # Longer delay on error
                
                # Update the match range for this player
                player_ranges[player_id] = start_index + MATCHES_PER_PLAYER
                print(f"Updated player {entry.get('riotIdGameName', 'Unknown')} to start at match {player_ranges[player_id]}")

            save_processed_matches(processed)
            save_player_match_ranges(player_ranges)
            print(f"Completed batch. Processed {len(processed)} total matches.")
            print(f"Sleeping {BATCH_DELAY} seconds before next round...")
            time.sleep(BATCH_DELAY)
            
        except KeyboardInterrupt:
            print("\nStopping data collection...")
            save_processed_matches(processed)
            save_player_match_ranges(player_ranges)
            break
        except Exception as e:
            print(f"Error in main loop: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main_loop()



