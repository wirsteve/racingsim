"""A message that says an action didn't happen (not enough money, no room, unknown option).

It is a plain string everywhere it's used; the server reports it with ``ok: false`` so the UI can show it
as an error instead of a confirmation."""


class Fail(str):
    pass
