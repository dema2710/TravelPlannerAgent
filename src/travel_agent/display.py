"""Human-readable terminal rendering of a validated travel plan."""

from __future__ import annotations

from travel_agent.schemas import TravelPlan
from travel_agent.utils.money import format_money


def format_plan(plan: TravelPlan) -> str:
    """Render the final plan as readable plain text."""
    request = plan.request
    currency = request.currency
    lines: list[str] = []
    separator = "=" * 72

    lines.append(separator)
    lines.append(f"TRAVEL PLAN - {request.destination.upper()}")
    lines.append(separator)
    lines.append(
        f"Dates: {request.start_date.isoformat()} to {request.end_date.isoformat()} "
        f"({request.days} days, {request.nights} nights)"
    )
    lines.append(f"Pace: {request.pace}")
    lines.append(f"Interests: {', '.join(request.interests)}")
    lines.append(
        "Dietary preferences: "
        + (", ".join(request.dietary_restrictions) if request.dietary_restrictions else "none specified")
    )
    lines.append(f"Budget: {format_money(request.budget, currency)}")
    lines.append("")
    lines.append("SUMMARY")
    lines.append(plan.summary)
    lines.append("")

    lines.append("SIMULATED WEATHER")
    for weather in plan.weather:
        lines.append(
            f"  {weather.date.isoformat()}  {weather.condition:<31} "
            f"{weather.min_temp_c:>4.0f}-{weather.max_temp_c:<4.0f} C  "
            f"precipitation {weather.precipitation_probability:>3}%"
        )
    lines.append("")

    flight = plan.selected_flight
    lines.append("FLIGHTS (round trip, one traveller) - SIMULATED")
    lines.append(f"  Airline: {flight.airline}")
    lines.append(
        f"  Departure: {flight.origin_city} ({flight.origin_airport}) | "
        f"Arrival: {flight.destination_city} ({flight.destination_airport})"
    )
    lines.append(
        f"  Outbound {flight.departure_date.isoformat()} "
        f"{flight.outbound_departure_time}-{flight.outbound_arrival_time} | "
        f"Return {flight.return_date.isoformat()} "
        f"{flight.return_departure_time}-{flight.return_arrival_time}"
    )
    lines.append(f"  Stops: {flight.stops} | Price: {format_money(flight.price, currency)}")
    lines.append("")

    hotel = plan.selected_accommodation
    lines.append("ACCOMMODATION - SIMULATED")
    lines.append(f"  {hotel.name} ({hotel.category}, rating {hotel.rating:.1f}/5)")
    lines.append(f"  {hotel.location}")
    lines.append(
        f"  {format_money(hotel.price_per_night, currency)} per night x {hotel.nights} "
        f"nights = {format_money(hotel.total_price, currency)}"
    )
    lines.append("")

    lines.append("DAILY ITINERARY - SIMULATED")
    for day in plan.daily_itinerary:
        lines.append("")
        lines.append(f"  Day {day.day_number} | {day.date.isoformat()} | {day.theme}")
        if day.activities:
            for activity in day.activities:
                lines.append(
                    f"    {activity.start_time}-{activity.end_time}  {activity.name}  "
                    f"[{format_money(activity.estimated_cost, currency)}]"
                )
                if activity.location:
                    lines.append(f"      Location: {activity.location}")
                lines.append(f"      {activity.description}")
        else:
            lines.append("    No paid activities scheduled. Free time / rest.")
        lines.append(
            f"    Food estimate: {format_money(day.daily_food_estimate, currency)} | "
            f"Local transport: {format_money(day.local_transport_estimate, currency)} | "
            f"Day total: {format_money(day.daily_total, currency)}"
        )
    lines.append("")

    budget = plan.budget_breakdown
    lines.append("BUDGET BREAKDOWN")
    lines.append(f"  Flights:               {format_money(budget.flights, currency):>16}")
    lines.append(f"  Accommodation:         {format_money(budget.accommodation, currency):>16}")
    lines.append(f"  Food:                  {format_money(budget.food, currency):>16}")
    lines.append(f"  Activities:            {format_money(budget.activities, currency):>16}")
    lines.append(f"  Local transportation:  {format_money(budget.local_transportation, currency):>16}")
    lines.append("  " + "-" * 48)
    lines.append(f"  Total estimated cost:  {format_money(budget.total_estimated_cost, currency):>16}")
    lines.append(f"  Budget:                {format_money(budget.budget, currency):>16}")
    lines.append(f"  Remaining budget:      {format_money(budget.remaining_budget, currency):>16}")
    status = "WITHIN BUDGET" if budget.budget_respected else "OVER BUDGET"
    lines.append(f"  Status:                {status:>16}")
    lines.append("")

    lines.append("RECOMMENDATIONS")
    for recommendation in plan.recommendations:
        lines.append(f"  - {recommendation}")
    lines.append("")
    lines.append("PRACTICAL NOTES")
    for note in plan.practical_notes:
        lines.append(f"  - {note}")
    lines.append("")
    lines.append("IMPORTANT DISCLAIMER")
    lines.append(f"  {plan.data_disclaimer}")
    lines.append(separator)
    return "\n".join(lines)
