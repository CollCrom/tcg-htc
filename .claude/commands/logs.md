Run a game with a specific seed and generate an HTML log viewer.

## Steps

1. Run the game with the given seed and capture the log:

```bash
python3 -c "
import logging, sys
sys.path.insert(0, 'src')
from pathlib import Path
from htc.cards.card_db import CardDatabase
from htc.engine.game import Game
from htc.player.random_player import RandomPlayer
from tests.integration.test_full_game import parse_markdown_decklist

logging.basicConfig(level=logging.INFO, format='%(message)s',
                    handlers=[logging.FileHandler('game_log.txt', mode='w'),
                              logging.StreamHandler()])

db = CardDatabase.load(Path('data/cards.tsv'))
cindra = parse_markdown_decklist(Path('ref/decklist-cindra-blue.md').read_text())
arakni = parse_markdown_decklist(Path('ref/decklist-arakni.md').read_text())
seed = $ARGUMENTS if '$ARGUMENTS'.strip() else 0
game = Game(db, cindra, arakni, RandomPlayer(seed=seed), RandomPlayer(seed=seed+100), seed=seed)
game.play()
ps = game.state.players
print(f'\nGame over — seed {seed}')
print(f'Cindra: {ps[0].life} life | Arakni: {ps[1].life} life')
print(f'Winner: {\"Cindra\" if game.state.winner == 0 else \"Arakni\" if game.state.winner == 1 else \"draw\"}')
"
```

2. Convert to HTML:
```bash
python3 -m tools.log_to_html game_log.txt game_log.html
```

3. Open the HTML file:
```bash
open game_log.html
```

4. Report the game result (winner, life totals, turn count) and tell the user the HTML is open.

If no seed is provided, default to seed 0.
