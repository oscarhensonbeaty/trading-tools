"""
rates_desk_toolkit.py

A small toolkit modelling the core workflow taught in Citi's Markets
Sales & Trading job simulation (Forage):

    1. Prepare a morning meeting brief from overnight market moves
    2. Analyse an FOMC (Federal Reserve) rate decision outcome
    3. Formulate a market view from that analysis
    4. Generate a trade idea that expresses the view
    5. Select a hedge to manage the trade's risk
    6. Produce a client-ready pitch combining all of the above

This is an educational/portfolio project, not a live trading system —
it does not connect to any market data feed or execute real trades.
All inputs are illustrative and meant to be swapped for real data.

Author: Oscar Henson-Beaty
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List


# ---------------------------------------------------------------------------
# 1. Morning meeting brief
# ---------------------------------------------------------------------------

@dataclass
class OvernightMove:
    """A single overnight market move to report in the morning meeting."""
    instrument: str          # e.g. "US 10Y Treasury Yield"
    change_bps_or_pct: float  # move size, in basis points (rates) or % (equities/FX)
    unit: str                 # "bps" or "%"
    commentary: str           # one-line driver of the move


@dataclass
class MorningBrief:
    """Aggregates overnight moves into a single desk-ready summary."""
    date: str
    moves: List[OvernightMove] = field(default_factory=list)

    def add_move(self, instrument: str, change: float, unit: str, commentary: str) -> None:
        self.moves.append(OvernightMove(instrument, change, unit, commentary))

    def summary(self) -> str:
        lines = [f"Morning Meeting Brief — {self.date}", "-" * 40]
        for m in self.moves:
            direction = "+" if m.change_bps_or_pct >= 0 else ""
            lines.append(
                f"{m.instrument:<25} {direction}{m.change_bps_or_pct}{m.unit:<4} — {m.commentary}"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 2. FOMC outcome analysis
# ---------------------------------------------------------------------------

class FOMCStance(Enum):
    HAWKISH = "Hawkish"   # more restrictive than expected — rates likely to stay higher / rise
    DOVISH = "Dovish"     # more accommodative than expected — rates likely to fall
    NEUTRAL = "Neutral"   # broadly in line with expectations


@dataclass
class FOMCOutcome:
    """Represents the result of an FOMC meeting against market expectations."""
    actual_rate_change_bps: float     # e.g. -25 for a 25bp cut, 0 for hold
    expected_rate_change_bps: float   # what the market had priced in beforehand
    statement_tone: str               # short paraphrase of statement language
    dot_plot_shift_bps: float = 0.0   # shift in projected future rate path, if any

    def classify_stance(self) -> FOMCStance:
        """
        Classify the outcome by comparing the actual decision (plus any
        forward guidance shift) against what was already priced in.
        A result more restrictive than expected is hawkish; more
        accommodative than expected is dovish.
        """
        surprise = self.actual_rate_change_bps - self.expected_rate_change_bps
        # A positive dot-plot shift (higher future path) reinforces a hawkish read
        combined_signal = surprise + (self.dot_plot_shift_bps * 0.5)

        if combined_signal > 5:
            return FOMCStance.HAWKISH
        elif combined_signal < -5:
            return FOMCStance.DOVISH
        return FOMCStance.NEUTRAL

    def analysis(self) -> str:
        stance = self.classify_stance()
        return (
            f"FOMC Outcome Analysis\n"
            f"{'-' * 40}\n"
            f"Actual change:   {self.actual_rate_change_bps:+.0f} bps\n"
            f"Expected change: {self.expected_rate_change_bps:+.0f} bps\n"
            f"Dot-plot shift:  {self.dot_plot_shift_bps:+.0f} bps\n"
            f"Statement tone:  {self.statement_tone}\n"
            f"Classified stance: {stance.value}\n"
        )


# ---------------------------------------------------------------------------
# 3 & 4. Market view -> Trade idea
# ---------------------------------------------------------------------------

class Direction(Enum):
    LONG = "Long"
    SHORT = "Short"


@dataclass
class TradeIdea:
    """A trade idea expressing a market view, with basic risk parameters."""
    instrument: str
    direction: Direction
    rationale: str
    entry_level: float
    target_level: float
    stop_level: float

    @property
    def reward_to_risk(self) -> float:
        reward = abs(self.target_level - self.entry_level)
        risk = abs(self.entry_level - self.stop_level)
        return round(reward / risk, 2) if risk else float("inf")

    def pitch_lines(self) -> List[str]:
        return [
            f"Trade: {self.direction.value} {self.instrument}",
            f"Rationale: {self.rationale}",
            f"Entry: {self.entry_level}  |  Target: {self.target_level}  |  Stop: {self.stop_level}",
            f"Reward-to-risk: {self.reward_to_risk}:1",
        ]


def generate_trade_idea(fomc: FOMCOutcome, instrument: str, current_level: float,
                         tick_size: float = 0.10) -> TradeIdea:
    """
    Turn an FOMC stance classification into a simple directional trade idea.

    Hawkish outcome -> yields likely rise -> short the price of a rate-sensitive
    instrument (e.g. a bond future), since bond prices fall as yields rise.
    Dovish outcome  -> yields likely fall -> long the instrument.
    Neutral         -> no directional edge; idea is flagged as low-conviction.
    """
    stance = fomc.classify_stance()

    if stance == FOMCStance.HAWKISH:
        direction = Direction.SHORT
        rationale = (
            "FOMC surprised hawkish relative to pricing; yields likely to grind "
            "higher, pressuring rate-sensitive instrument prices lower."
        )
        target = current_level - (tick_size * 20)
        stop = current_level + (tick_size * 8)
    elif stance == FOMCStance.DOVISH:
        direction = Direction.LONG
        rationale = (
            "FOMC surprised dovish relative to pricing; yields likely to ease, "
            "supporting rate-sensitive instrument prices higher."
        )
        target = current_level + (tick_size * 20)
        stop = current_level - (tick_size * 8)
    else:
        direction = Direction.LONG  # default flat-bias placeholder
        rationale = (
            "Outcome broadly in line with expectations — low-conviction idea; "
            "consider range-trading or standing aside until a clearer catalyst."
        )
        target = current_level + (tick_size * 5)
        stop = current_level - (tick_size * 5)

    return TradeIdea(
        instrument=instrument,
        direction=direction,
        rationale=rationale,
        entry_level=current_level,
        target_level=round(target, 2),
        stop_level=round(stop, 2),
    )


# ---------------------------------------------------------------------------
# 5. Hedge selection
# ---------------------------------------------------------------------------

@dataclass
class Hedge:
    instrument: str
    direction: Direction
    size_ratio: float   # size of hedge relative to the primary trade (e.g. 0.5 = half size)
    rationale: str

    def pitch_lines(self) -> List[str]:
        return [
            f"Hedge: {self.direction.value} {self.instrument} at {self.size_ratio:.0%} of primary size",
            f"Rationale: {self.rationale}",
        ]


def select_hedge(trade: TradeIdea, correlated_instrument: str) -> Hedge:
    """
    Select a simple offsetting hedge in a correlated instrument, opposite
    direction to the primary trade, at partial size — mirroring the
    reduce-net-risk logic taught in the simulation's hedging task.
    """
    hedge_direction = Direction.SHORT if trade.direction == Direction.LONG else Direction.LONG
    return Hedge(
        instrument=correlated_instrument,
        direction=hedge_direction,
        size_ratio=0.5,
        rationale=(
            f"Partial offsetting position in {correlated_instrument} to reduce "
            f"net directional exposure if the {trade.instrument} view is wrong, "
            f"while retaining most of the intended risk/reward."
        ),
    )


# ---------------------------------------------------------------------------
# 6. Client-ready pitch
# ---------------------------------------------------------------------------

def build_client_pitch(brief: MorningBrief, fomc: FOMCOutcome,
                        trade: TradeIdea, hedge: Hedge) -> str:
    lines = [
        brief.summary(),
        "",
        fomc.analysis(),
        "Trade Idea",
        "-" * 40,
        *trade.pitch_lines(),
        "",
        "Suggested Hedge",
        "-" * 40,
        *hedge.pitch_lines(),
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Example run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # 1. Morning brief
    brief = MorningBrief(date="2026-08-30")
    brief.add_move("US 10Y Treasury Yield", 6, "bps", "Rose on hot overnight inflation print")
    brief.add_move("S&P 500 Futures", -0.4, "%", "Softer ahead of FOMC decision")
    brief.add_move("USD Index (DXY)", 0.3, "%", "Dollar firmer on rate expectations")

    # 2. FOMC outcome — a hold that was more hawkish than the market had priced
    fomc = FOMCOutcome(
        actual_rate_change_bps=0,
        expected_rate_change_bps=-10,     # market had priced in some chance of a cut
        statement_tone="Committee removed easing bias language versus prior meeting",
        dot_plot_shift_bps=15,            # projected path nudged higher
    )

    # 3 & 4. Market view -> trade idea
    trade = generate_trade_idea(fomc, instrument="10Y Treasury Future", current_level=112.50)

    # 5. Hedge
    hedge = select_hedge(trade, correlated_instrument="5Y Treasury Future")

    # 6. Full client pitch
    print(build_client_pitch(brief, fomc, trade, hedge))
