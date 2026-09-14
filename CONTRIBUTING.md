# Contributing

This repo is meant to become **public**. Treat every commit as if a
stranger will read it.

## Do not commit

- Application source copied from another company or client repo
- Internal service names, product codenames, customer names, ticket IDs
- `.env`, tokens, cloud keys, `docker-compose` with real passwords
- SQL, fiscal rules, or any domain that is not a **generic Go example**
- Screenshots, logs, or quality bundles (`.quality/`) from a private app

If a file would not make sense to a random Go team, it does not belong here.

## Do commit

- Engine, CLI, review steps, install/setup flow
- Generic hunters (e.g. Go `testing` asserts, complexity on **new** funcs)
- Docs that describe the ritual without naming a vendor product

When in doubt, leave it out or rewrite the example from scratch.
