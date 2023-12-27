import numpy as np
import pandas as pd
from pathlib import Path
import streamlit as st
import re
from itertools import zip_longest
import sqlite3

st.set_page_config(layout="wide")

st.title("Coinche-moi STP")

# url = "https://raw.githubusercontent.com/Puumanamana/coinche/main/assets/cards"

cards = [Path("assets", "cards", f"{suit}_{value}.png")
         for suit in ["hearts", "diamonds", "spades", "clubs"]
         for value in ["7", "8", "9", "10", "jack", "queen", "king", "ace"]]
suits = {x: x.stem.split('_')[0] for x in cards}
symbols = dict(spades="♠", hearts="♥", diamonds="♦", clubs="♣", sans_atout="SA", tout_atout="TA")
suit_fmt = dict(spades="Pique", hearts="Coeur", diamonds="Carreau", clubs="Trèfle",
                sans_atout="Sans atout", tout_atout="Tout atout")

conn = sqlite3.connect('coinche.db')
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS coinche(hand, guess, suit, comment)")
conn.commit()
conn.close()


def get_db():
    df = pd.read_sql(
        "SELECT * FROM coinche",
        con=sqlite3.connect('coinche.db'),
    )
    return df.iloc[::-1]

def save_to_db(guess, suit, comment):
    db_entry = (
        ",".join(x.stem for x in st.session_state.hand),
        guess, suit, comment
    )
    conn = sqlite3.connect('coinche.db')
    c = conn.cursor()
    c.execute("INSERT INTO coinche (hand, guess, suit, comment) VALUES (?, ?, ?, ?)", db_entry)
    conn.commit()

    # Close connection
    conn.close()

def update_hand():
    st.session_state["hand"] = np.random.choice(cards, 8, replace=False)

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

tabs = st.tabs(["Jouer", "Historique"])

with tabs[0]:
    update_hand = st.button("Prochaine main", on_click=update_hand, type="primary")

    if not "hand" in st.session_state:
        st.stop()

    st.image(sort_hand(st.session_state.hand), width=170)

    layout, _ = st.columns([1, 1])
    with layout:
        col1, col2 = st.columns([1, 1])
        with col1:
            guess = st.number_input(
                "Choisir une annonce : ", key="guess",
                min_value=0, max_value=270, value=80, step=10
            )
        with col2:
            suit = st.selectbox(
                "Choisir une couleur : ",
                suit_fmt, format_func=lambda x: suit_fmt[x],
                index=None, key="suit", placeholder="Pas d'annonce"
            )

        comment = st.text_area("Ajouter un commentaire :", key="comment")

        submitted = st.button("Valider", on_click=save_to_db, args=(guess, suit, comment))

        if submitted:
            if suit:
                st.success(f"Mise enregistrée : {guess} {symbols[suit]}")
            else:
                st.success(f"Mise enregistrée : Passer")

with tabs[1]:
    df = get_db()

    for row in df.itertuples():
        hand = [Path("assets", "cards", f"{card}.png") for card in row.hand.split(",")]
        st.image(sort_hand(hand), width=170)
        st.metric(label="Mise", value=f"{row.guess} {symbols.get(row.suit)}" if row.suit else "Pas d'annonce")
        if row.comment:
            st.write(f"Commentaire: {row.comment}")
        st.divider()
