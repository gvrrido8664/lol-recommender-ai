from pathlib import Path
p=Path(r'C:\Riot Games\League of Legends\Config\LeagueClientSettings.yaml')
print('exists', p.exists())
if p.exists():
    print(p)
    with p.open('r', encoding='utf-8', errors='ignore') as f:
        for i, line in enumerate(f):
            if i >= 40:
                break
            print(line.rstrip())
