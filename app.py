import numpy as np
import pandas as pd
from pathlib import Path
import streamlit as st
import re
from itertools import zip_longest
import sqlite3

st.set_page_config(layout="wide")

st.title("Coinche-moi STP")

# ------- Global vars
# url = "https://raw.githubusercontent.com/Puumanamana/coinche/main/assets/cards"

cards = [Path("assets", "cards", f"{suit}_{value}.png")
         for suit in ["hearts", "diamonds", "spades", "clubs"]
         for value in ["7", "8", "9", "10", "jack", "queen", "king", "ace"]]

suits = {x: x.stem.split('_')[0] for x in cards}
symbols = dict(spades="♠", hearts="♥", diamonds="♦", clubs="♣", sans_atout="SA", tout_atout="TA")
suit_fmt = dict(spades="Pique", hearts="Coeur", diamonds="Carreau", clubs="Trèfle",
                sans_atout="Sans atout", tout_atout="Tout atout")


# ------- Initalize DB
conn = sqlite3.connect('coinche.db')
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS coinche(hand, guess, suit, comment)")
conn.commit()
conn.close()

db_df = pd.read_sql(
    "SELECT * FROM coinche",
    con=sqlite3.connect('coinche.db'),
).astype({"guess": "Int64"})


# ------- Admin panel

st.markdown("#### Paramètres administrateur")
admin_cols = st.columns([1, 1, 4])

with admin_cols[0]:
    train_mode = st.toggle("Mode entrainement", key="train")

with open('coinche.db', 'rb') as f:
    with admin_cols[1]:
        st.download_button('Download database', f, file_name='coinche.db')

if train_mode:
    np.random.seed(42)
    train_hands = [np.random.choice(cards, 8, replace=False) for _ in range(200)]

# ------- Utility functions
def format_hand_for_db(hand):
    return ",".join(Path(x).stem for x in hand)

def save_to_db(guess, suit, comment, passer):

    if passer:
        db_entry = (
            format_hand_for_db(st.session_state.hand),
            None, None, comment
        )
    else:
        db_entry = (
            format_hand_for_db(st.session_state.hand),
            guess, suit, comment
        )
    print("Saving: {}".format(db_entry))
    conn = sqlite3.connect('coinche.db')
    c = conn.cursor()
    c.execute("INSERT INTO coinche (hand, guess, suit, comment) VALUES (?, ?, ?, ?)", db_entry)
    conn.commit()

    # Close connection
    conn.close()

def sort_hand(hand):
    hand_df = pd.Series([card.stem for card in hand]).str.split("_", expand=True)
    hand_df.index = hand
    hand_df.columns = ["suit", "number"]
    hand_df["color"] = np.where(hand_df["suit"].isin(["hearts", "diamonds"]), "red", "black")

    # Find the most common color
    suits_found = hand_df.groupby("color").suit.agg(set)
    color_max = suits_found.map(len).idxmax()
    # Other color ('manually' set since all colors are not always present)
    other_color = [color for color in {"red", "black"} if color != color_max][0]

    # Alternate colors
    suit_order = [
        suit
        for suits in zip_longest(suits_found[color_max], suits_found[other_color])
        for suit in suits if suit is not None
    ]

    # Category order
    hand_df["suit"] = pd.Categorical(hand_df["suit"], suit_order)

    return hand_df.sort_values(["suit", "number"], ascending=False).index.astype(str).to_list()

def update_hand():
    if st.session_state.get("train", False):
        try:
            hand = train_hands[st.session_state.get("hand_idx", 0)]
            st.session_state["hand_idx"] = st.session_state.get("hand_idx", 0) + 1
        except IndexError:
            st.success("Fin de l'entrainement. Selectionnez \"Prochaine main\" pour recommencer")
            st.session_state["hand_idx"] = 0
            return
        st.success("Main numero {}".format(st.session_state["hand_idx"]))
    else:
        hand = np.random.choice(cards, 8, replace=False)
    st.session_state["hand"] = sort_hand(hand)

def guess_menu():
    layout, _ = st.columns([1, 1])
    with layout:
        col1, col2 = st.columns([1, 1])
        passer = st.toggle("Passer")
        with col1:
            guess = st.number_input(
                "Choisir une annonce : ", key="guess",
                disabled=passer,
                min_value=0, max_value=270, value=80, step=10
            )
        with col2:
            suit = st.selectbox(
                "Choisir une couleur : ",
                suit_fmt, format_func=lambda x: suit_fmt[x], disabled=passer,
                key="suit"
            )

        comment = st.text_area("Ajouter un commentaire :", key="comment")

        submitted = st.button("Valider", key="submitted", on_click=save_to_db, args=(guess, suit, comment, passer))

        if submitted:
            if not passer:
                st.success(f"Mise enregistrée : {guess} {symbols[suit]}")
            else:
                st.success(f"Mise enregistrée : Passe")

def show_stats():
    db_entry = db_df[db_df.hand.str.contains(format_hand_for_db(st.session_state.hand))]

    if db_entry.empty:
        value = "Not in database"
        sd = None
        n_votes = 0
    else:
        annonces = db_entry.guess.astype(str).str.cat(
            db_entry.suit.map(lambda x: symbols.get(x)), sep=" "
        ).fillna("Passe")
        value = annonces.mode().iloc[0]
        sd = db_entry.guess.std()
        if pd.isnull(sd):
            sd = 0
        n_votes = db_entry.shape[0]

    s = "s" if n_votes > 1 else ""
    st.metric(value=value, label=f"Annonce la plus populaire [{n_votes} vote{s}]", delta=sd)


# ------- Main app
tabs = st.tabs(["Jouer", "Historique"])

with tabs[0]:
    st.button("Prochaine main", on_click=update_hand, type="primary")

    if "hand" in st.session_state:
        st.image(st.session_state.hand, width=170)
        guess_menu()
    if st.session_state.get("submitted", False):
        show_stats()

with tabs[1]:
    st.subheader("Historique des 10 dernières mains")

    for row in db_df.tail(10).iloc[::-1].itertuples():
        hand = [Path("assets", "cards", f"{card}.png") for card in row.hand.split(",")]
        st.image(sort_hand(hand), width=170)
        st.metric(label="Mise", value=f"{row.guess} {symbols.get(row.suit)}" if row.suit else "Passe")
        if row.comment:
            st.write(f"Commentaire: {row.comment}")
        st.divider()
