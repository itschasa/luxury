# Luxury Code Base

As this project is now permanently closed/stopped, I've decided to release the source code, with the aim of allowing people to learn from it.

Luxury, LuxuryNitro, LuxuryBoosts were a set of services linked with Discord.

If you have any questions, make an issue on this repo, or join my [Discord Server](https://discord.gg/bjzADG4C4s).

These projects are not really designed to be "plug 'n' play". You can attempt to run them for yourself, however I will not be providing extensive support for it.

Pull requests editing code will not be accepted. However, if you want to make a PR adding more documentation, please feel free.


## Repos
- `/nitro/` - Nitro Sniping Service (dash.luxurynitro.com)
    - `/nitro/site/` - Website (Python, HTML, JS) ([README](https://github.com/itschasa/luxury/blob/main/nitro/site/README.md))
    - `/nitro/sniper/` - Sniper (Go) ([README](https://github.com/itschasa/luxury/blob/main/nitro/sniper/README.md))
        - `/nitro/sniper/auth_server/` - Authentication Server (Python) (was never used)
- `/members/` - Boost + Fake Members Service (mem.luxurynitro.com) ([README](https://github.com/itschasa/luxury/blob/main/members/README.md))
    - `/members/public/` - Frontend Site (HTML, JS)
    - `/members/private/` - Backend (Python)
- `/helper/` - AI Powerered Discord Chat Bot ([README](https://github.com/itschasa/luxury/blob/main/helper/README.md))

The `/gallery/` folder contains images of the different projects in action.



## Terminology
- Nitro Sniping
    - Bots watching public chat channels for Nitro Gift links, and redeeming them on an account within milliseconds.
    - You can obtain Nitro cheaper this way.
- Fake Members
    - Bot accounts joining a Discord Server, to elevate it's member count. Can be offline, or online.
    - Makes the server (at first glance) seem more popular than it is.
- Boosting Service
    - Allows the user to have their server (Nitro) boosted by bots, to get to a higher level, and get the entire server perks (like a vanity invite link).
    - Cheaper this way, than buying Nitro/Boosts.

