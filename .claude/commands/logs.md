Run a game with a specific seed and generate an HTML log viewer.

The argument should be a numeric seed (e.g., `/logs 42`). Defaults to seed 0 if not provided.

## Steps

1. Parse the seed from the arguments. If `$ARGUMENTS` is empty or not provided, use seed 0. If it's not a valid number, tell the user and ask for a numeric seed.

2. Run the game and capture the log:

```bash
python3 -c "
import logging, sys
from pathlib import Path
from engine.cards.card_db import CardDatabase
from engine.rules.game import Game
from engine.player.random_player import RandomPlayer
from tests.integration.test_full_game import parse_markdown_decklist

seed = int(sys.argv[1])
logging.basicConfig(level=logging.INFO, format='%(message)s',
                    handlers=[logging.FileHandler('game_log.txt', mode='w'),
                              logging.StreamHandler()])

db = CardDatabase.load(Path('data/cards.tsv'))
cindra = parse_markdown_decklist(Path('ref/decks/decklist-cindra-blue.md').read_text())
arakni = parse_markdown_decklist(Path('ref/decks/decklist-arakni.md').read_text())
game = Game(db, cindra, arakni, RandomPlayer(seed=seed), RandomPlayer(seed=seed+100), seed=seed)
game.play()
ps = game.state.players
print(f'\nGame over — seed {seed}')
print(f'Cindra: {ps[0].life} life | Arakni: {ps[1].life} life')
w = game.state.winner
print(f'Winner: {\"Cindra\" if w == 0 else \"Arakni\" if w == 1 else \"draw\"}')
" SEED
```

Replace `SEED` with the parsed seed number.

3. Convert to HTML:
```bash
python3 -m tools.log_to_html game_log.txt game_log.html
```

4. Open the HTML file:
```bash
open game_log.html
```

5. Report the game result (winner, life totals, turn count) and tell the user the HTML is open.
