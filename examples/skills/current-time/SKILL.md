---
name: current-time
description: Report the current date and time. Use when the user asks what time it is, what day it is, or how many days until something.
version: 0.1.0
---

# Current Time

## When to Use

- User asks "what time is it," "what day is it," "what's today's date"
- User asks about time elapsed since or remaining until a specific date

## Procedure

1. Determine the relevant timezone. Use the agent's configured timezone unless the user specifies otherwise.
2. Report the current time in a natural, concise form (e.g. "It's 3:42 PM on Saturday, May 9").
3. For countdowns, compute days/hours between `now` and the target date.

## Pitfalls

- Don't guess the timezone. If unclear, say the zone you're reporting in.
- 24-hour vs 12-hour: match the user's apparent convention.
- "Now" is the container's system time — if the host clock is wrong, so is the answer.

## Verification

A good reply names the day of the week, the date, and the time to the minute.
