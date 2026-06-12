import json
import random

champions = [
    {"id": "62", "name": "Wukong"},
    {"id": "86", "name": "Garen"},
    {"id": "122", "name": "Darius"},
    {"id": "157", "name": "Yasuo"}
]

games = []
for i in range(15):
    win = random.choice([True, False])
    kills = random.randint(2, 12)
    deaths = random.randint(1, 9)
    assists = random.randint(5, 15)
    cs = random.randint(100, 250)
    dur = random.randint(1200, 2400)
    champ = random.choice(champions)["id"]
    fb = random.choice([True, False])
    vision = random.randint(5, 30)
    
    game = {
        "gameId": 1000000 + i,
        "gameDuration": dur,
        "gameCreation": 1690000000000 + i * 10000000,
        "participants": [
            {
                "championId": int(champ),
                "stats": {
                    "win": win,
                    "kills": kills,
                    "deaths": deaths,
                    "assists": assists,
                    "totalMinionsKilled": cs,
                    "neutralMinionsKilled": 0,
                    "visionScore": vision,
                    "firstBloodKill": fb
                }
            }
        ]
    }
    games.append(game)

data = {
    "identidad": {
        "nombre": "Mock Player",
        "nivel": 150,
        "icono": 4000,
        "soloq": {"tier": "GOLD", "division": "II", "lp": 50, "wins": 120, "losses": 110},
        "flex": {"tier": "SILVER", "division": "I", "lp": 99, "wins": 45, "losses": 40}
    },
    "historial": games
}

with open("src/mock_data.json", "w") as f:
    json.dump(data, f, indent=4)
print("Mock data generated at src/mock_data.json")
