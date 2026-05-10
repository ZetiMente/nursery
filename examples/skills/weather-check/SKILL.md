---
name: weather-check
description: Check current weather or forecast for a location. Use when the user asks about temperature, rain, snow, wind, or general conditions.
version: 0.1.0
---

# Weather Check

## When to Use

- User asks "what's the weather," "is it raining," "do I need a coat"
- User mentions an outdoor plan where conditions matter
- Any question referencing current or upcoming weather

## Procedure

1. Extract a location from the message (city, zip, or "here" implying the user's known location).
2. Call a weather API (Open-Meteo has no key required; NWS for US).
3. Report temperature, conditions, and one relevant detail (wind, humidity, precipitation chance) — no more.

## Pitfalls

- Don't invent numbers; if the API fails, say so clearly.
- Units: match the user's locale (°F for US, °C elsewhere) unless they specify.
- If the user didn't name a location and we don't have one, ask.

## Verification

A good reply answers in one sentence with real numbers and acknowledges the location.
