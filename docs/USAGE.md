# What you can ask for

How each request is handled, in full. The README carries the short table; this is the version worth
reading before you rely on one of these.

## Finding out what is going on

**"What's on air right now?"**
The track, the show, the host, and whether the station is actually streaming.

**"What changed since last week?"**
Compares your files against the live station and lists what differs, by host, by show, by hour of the
week. Asking changes nothing.

## Fixing how a host sounds

**"Why does <host> talk so much?"**
Reads that host's dials, their written character and the shows they present, then proposes the smallest
change that would fix it. It does not guess: if the answer is "that show is set to talk a lot", it says
so and shows you the setting.

**"Make <host> warmer"** or **"make this show less chatty"**
Changes that one setting, checks the result, and shows you before and after. Nothing goes live until you
say so.

## Adding people and programmes

**"Add a host"**
Scaffolds a new host — but it asks you to describe the character first, because a host's soul *is* the
prompt the DJ writes from. A blank soul produces a blank presenter.

**"Make me a new show"**, then **"put it on Sunday mornings"**
Creates the show and fills the hours you name in the weekly grid, showing you which cells it changes and
which it would take from another show.

## Keeping things out

**"Stop playing <artist>"**
Adds a ban. Bans apply to the whole station, or only while a particular show is on air.

**"Block Christmas music until December"**
Worth reading twice: a seasonal rule's window is **when the rule is paused**, not when it applies. A
December window means the ban is off during December and on for the other eleven months. If you want it
the other way round, say so.

## Protecting the station

**"Back up the station"**
Copies the settings, the shows, the schedule, the station's skills and its media manifests, and writes a
note saying where each file goes back. Deliberately more than the console's export, which leaves out the
schedule — and so loses every show and the whole grid. It needs host access: without it the tool refuses
rather than hand you a backup that could not restore the programming.

**"Put the station back to what's in git"**
Sends your files to the station. It shows you every change first and sends nothing until you confirm.

**"Undo the last change"**
Puts a backup back, or applies an earlier commit — depending on whether you want the station as it was
ten minutes ago or last week.

## Live, right now

**"Say something on air"**, **"skip this track"**, **"play a jingle"**
These change what is happening this second. They are the only things here that do, they need your
explicit go-ahead each time, and a skip also needs to know which track you meant — or your permission to
skip whatever is playing.

## Where the procedure lives

Each of these has a rehearsed procedure in `skills/<name>/SKILL.md`: `add-host`, `new-show`,
`explain-host`, `tune-host` and `backup`. The verb decides which one loads; anything that changes the
station still ends at `validate`, a dry run and `apply --yes`.
