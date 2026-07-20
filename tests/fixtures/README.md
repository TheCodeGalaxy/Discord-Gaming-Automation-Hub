# Test Fixtures

This directory contains static JSON response files that mimic real provider API responses. They are used by provider unit tests to verify response parsing without hitting real endpoints.

## Structure

```
fixtures/
├── cheapshark/
│   ├── deals.json
│   ├── games.json
│   └── game_detail.json
├── epic/
│   ├── free_games.json
│   ├── upcoming_games.json
│   └── search_results.json
├── steam/
│   ├── appdetails.json
│   └── trending.json
└── isthereanydeal/
    ├── search.json
    ├── deals.json
    └── lowest.json
```

## Adding New Fixtures

1. Make a real API call (e.g., `curl https://www.cheapshark.com/api/1.0/deals?limit=1`).
2. Save the response body as a `.json` file in the appropriate subdirectory.
3. Reference it in your provider unit test via `fixtures_path()` helper.
