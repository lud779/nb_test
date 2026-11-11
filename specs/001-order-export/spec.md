# Export matched orders

An operator exports all matched orders from the orders list.

- **FR-001** The API returns a `download_url` string and the export status.
- **FR-002** Export returns all 120 matching orders, even though the list displays 20 per page.
- **SC-001** The contract and browser E2E checks both pass for the candidate commit.

The check-specific requirements live in [contract.json](./contract.json) and [export.json](./export.json).
