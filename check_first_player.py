# Quick analysis of who played first
print("Analiza kto grał pierwszy:")
print("=" * 50)

games = [
    ("Gra 1", "Claude", "2 → (2,2)"),
    ("Gra 2", "Claude", "8 → (2,2)"),
    ("Gra 3", "Claude", "5 → (2,2)"),
    ("Gra 4", "Claude", "4 → (2,2)"),
    ("Gra 5", "Claude", "8 → (2,2)"),
    ("Gra 6", "Claude", "6 → (2,2)"),
    ("Gra 7", "Claude", "6 → (2,2)"),
    ("Gra 8", "Claude", "8 → (2,2)"),
    ("Gra 9", "Claude", "4 → (2,2)"),
    ("Gra 10", "Claude", "6 → (2,2)")
]

for game, player, move in games:
    print(f"{game}: {player} rozpoczął ({move})")

print("\n" + "=" * 50)
print(f"Claude zaczynał: 10/10 gier (100%)")
print(f"OpenAI zaczynał: 0/10 gier (0%)")
print("\n⚠️ TO JEST OGROMNA PRZEWAGA DLA CLAUDE!")
