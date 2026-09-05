# Roblox Obby Starter (Luau)

A small, coherent obby starter written in Luau. One server-authoritative finish loop,
one `leaderstats/StagesCompleted` IntValue, one client win screen, and one `RemoteEvent`
for client->server Continue/Restart calls.

Scope notes (read this first):
- This is a starter, not a full game. It gives you one working obby loop: touch the stage
  Begin, then touch that stage's Finish, and the server advances you to the next stage's
  Begin (or back to Start if you finished the last stage).
- Server-authoritative. The client cannot fake a win. The server checks the player's current
  stage, whether they touched the Begin of that stage this round, and then decides.
- No DataStore persistence in this starter. `leaderstats` and per-player state reset on
  leave. That keeps it small. Add persistence later if you want it.
- Win screen: the server fires `showwin` to the client on a real finish, and `hidewin`
  when it moves/respawns the player, so the GUI works out of the box.

## Studio project structure

Drop these into Roblox Studio exactly as shown. The script code uses these paths and names,
so if you rename anything, match the code.

```
Workspace
  Obby                 ▸ Folder
    Start              ▸ Part (spawn anchor / first start pad)
    Stages             ▸ Folder
      Stage1           ▸ Model (one stage)
        Begin          ▸ Part (start pad for this stage, CanTouch = true)
        Finish         ▸ Part (win touch, CanTouch = true)
      Stage2           ▸ Model (duplicate Stage1 for more stages)
        Begin
        Finish

ReplicatedStorage
  ObbyRemote           ▸ RemoteEvent (client -> server: continue/restart)

ServerScriptService
  ObbyServer           ▸ Script (server logic)

StarterGui
  WinGui               ▸ ScreenGui
    WinFrame           ▸ Frame (Visible = false by default)
      TitleLabel       ▸ TextLabel
      ContinueButton   ▸ TextButton
      RestartButton    ▸ TextButton
      LocalScript      ▸ LocalScript (client logic)
```

## What each piece does

### Workspace / Obby
- `Start`: the first spawn point. On join the server puts the player near it.
- `Stages/StageN/Begin`: touch this once this round to mark the player as "in round" for
  this stage.
- `Stages/StageN/Finish`: touch this after touching the matching Begin to win the stage.
  The server then advances the player to the next Begin, or back to Start if the last stage
  was finished.

Add more stages with **File > Save As** or by duplicating `Stage1` in the Explorer and
renaming it `Stage2`, `Stage3`, etc. The server scans `Workspace.Obby.Stages`, picks up any
Model with a `Begin` and a `Finish`, and sorts them by name, so `Stage1, Stage2, Stage3` is
the run order.

### ReplicatedStorage / ObbyRemote
A single RemoteEvent used by the client to tell the server about Continue/Restart choices.
The server never trusts the client's stage state; it still enforces the win rules.

### ServerScriptService / ObbyServer
The server Script. It:
- creates `leaderstats/StagesCompleted` for each player
- tracks each player's current stage index and whether they touched the Begin of that stage
  this round
- on touching the matching Finish, increments `StagesCompleted`, shows the client win screen,
  then moves the player to the next stage's Begin (or back to Start if finished)
- handles the client's Continue/Restart remote calls without trusting client state

### StarterGui / WinGui / WinFrame / LocalScript
The client LocalScript. It shows a win Frame with a TitleLabel, ContinueButton, and
RestartButton. Show is driven by the server via `showwin`/`hidewin` on the RemoteEvent.
Continue and Restart fire the RemoteEvent back to the server.

## Where to drop each script

- **ObbyServer**: ServerScriptService, new Script, paste the server Luau, name it `ObbyServer`.
- **WinGui LocalScript**: StarterGui > WinGui > WinFrame, add a LocalScript, paste the client
  Luau.
- **ObbyRemote**: ReplicatedStorage, insert a RemoteEvent, name it `ObbyRemote`.
- **Workspace obby**: Workspace > Obby folder > Start part, and Obby > Stages > Stage1 Model
  with Begin and Finish parts inside (then duplicate for more stages).

## How to play / test in Studio

1. Build the structure above in Roblox Studio. Set `Finish.CanTouch = true` on each stage's
   Finish part. Make Begin and Start normal parts the player can stand on.
2. Press **Play**. Your local character joins and spawns near `Obby/Start`.
3. Walk to `Stages/Stage1/Begin`, touch it, then reach `Stages/Stage1/Finish`. The server
   increments `StagesCompleted` and shows the win screen, then moves you to the next stage's
   Begin (or back to Start if Stage1 was the only stage).
4. Add more stages by duplicating `Stage1` in the Explorer and rebuilding the gap between
   each Begin and Finish.
5. During testing you can reset with the Restart button on the win screen.

## Notes
- The client win screen is driven by the server; it is not a local "I touched finish" popup.
  That keeps the win server-authoritative.
- If you want persistence later, add a DataStore read/write in ObbyServer around
  `Players.PlayerAdded` and `Players.PlayerRemoving`.
