-- ServerScriptService.ObbyServer
-- Small, server-authoritative obby starter.
-- Workspace.Obby/Start              - first spawn anchor (Part)
-- Workspace.Obby/Stages/StageN     - Model with Begin + Finish parts
-- ReplicatedStorage.ObbyRemote     - client -> server Continue/Restart
-- leaderstats/StagesCompleted      - IntValue, incremented on a real finish

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local ObbyRemote = ReplicatedStorage:WaitForChild("ObbyRemote")
local Obby = Workspace:WaitForChild("Obby")
local StartPart = Obby:WaitForChild("Start")
local StagesFolder = Obby:WaitForChild("Stages")

-- Collect every stage Model that has a Begin and a Finish. Sort by name so
-- Stage1, Stage2, Stage3 is the run order.
local function findStages()
	local stages = {}
	for _, child in ipairs(StagesFolder:GetChildren()) do
		if child:IsA("Model") and child:FindFirstChild("Begin") and child:FindFirstChild("Finish") then
			table.insert(stages, child)
		end
	end
	table.sort(stages, function(a, b)
		return a.Name < b.Name
	end)
	return stages
end

local stages = findStages()

local function totalStages()
	return #stages
end

-- Per-player state.
local currentStage = {}   -- player -> 1-based stage index they are on
local inRound = {}        -- player -> true once they touched the Begin of that stage this round

local function setLeaderstat(player, value)
	local ls = player:FindFirstChild("leaderstats")
	if ls then
		local v = ls:FindFirstChild("StagesCompleted")
		if v then
			v.Value = value
		end
	end
end

local function spawnAt(player, stageIndex)
	local target
	if stageIndex >= 1 and stageIndex <= totalStages() and stages[stageIndex] then
		target = stages[stageIndex]:FindFirstChild("Begin")
	else
		target = StartPart
	end
	if target and target:IsA("BasePart") and player.Character then
		local root = player.Character:FindFirstChild("HumanoidRootPart")
		if root then
			root.CFrame = target.CFrame + Vector3.new(0, 3, 0)
		end
	end
end

local function resetPlayer(player)
	currentStage[player] = 1
	inRound[player] = false
	ObbyRemote:FireClient(player, "hidewin")
	if player.Character then
		spawnAt(player, 1)
	end
end

-- Give each new player a leaderstat and start them at stage 1.
Players.PlayerAdded:Connect(function(player)
	local ls = Instance.new("Folder")
	ls.Name = "leaderstats"
	ls.Parent = player

	local completed = Instance.new("IntValue")
	completed.Name = "StagesCompleted"
	completed.Value = 0
	completed.Parent = ls

	currentStage[player] = 1
	inRound[player] = false

	player.CharacterAdded:Connect(function()
		task.wait()
		if currentStage[player] then
			spawnAt(player, currentStage[player])
		end
	end)
end)

-- Track who touched the Begin of their current stage this round.
local beginConn = {}
local function attachBegin(stage)
	if beginConn[stage] then
		beginConn[stage]:Disconnect()
	end
	beginConn[stage] = stage.Begin.Touched:Connect(function(hit)
		local char = hit.Parent
		if not char then return end
		local humanoid = char:FindFirstChild("Humanoid")
		if not humanoid then return end
		local player = Players:GetPlayerFromCharacter(char)
		if not player then return end
		if not currentStage[player] then return end

		local stageIndex = currentStage[player]
		if stageIndex < 1 or stageIndex > totalStages() then return end
		local stageForPlayer = stages[stageIndex]
		if stageForPlayer ~= stage then return end
		if inRound[player] then return end

		inRound[player] = true
	end)
end

for _, stage in ipairs(stages) do
	attachBegin(stage)
end

-- Track who touched the Finish for each stage. This is the win path and is
-- server-authoritative.
local finishConn = {}
local function attachFinish(stage)
	if finishConn[stage] then
		finishConn[stage]:Disconnect()
	end
	finishConn[stage] = stage.Finish.Touched:Connect(function(hit)
		local char = hit.Parent
		if not char then return end
		local humanoid = char:FindFirstChild("Humanoid")
		if not humanoid then return end
		local player = Players:GetPlayerFromCharacter(char)
		if not player then return end
		if not currentStage[player] then return end

		local stageIndex = currentStage[player]
		if stageIndex < 1 or stageIndex > totalStages() then return end
		local stageForPlayer = stages[stageIndex]
		if stageForPlayer ~= stage then return end
		if not inRound[player] then return end

		-- Real finish. Increment, show the client win screen, then advance.
		inRound[player] = false

		local completed = 0
		local ls = player:FindFirstChild("leaderstats")
		if ls then
			local v = ls:FindFirstChild("StagesCompleted")
			if v then
				completed = v.Value
			end
		end
		completed = completed + 1
		setLeaderstat(player, completed)

		ObbyRemote:FireClient(player, "showwin", stage.Name)

		if stageIndex < totalStages() then
			currentStage[player] = stageIndex + 1
			spawnAt(player, currentStage[player])
		else
			currentStage[player] = 1
			spawnAt(player, 1)
		end
	end)
end

for _, stage in ipairs(stages) do
	attachFinish(stage)
end

-- Client Continue/Restart. Server still enforces the obby logic; the client
-- only asks. Restart forces a reset. Continue is a no-op here because the real
-- progression happens on a Finish touch (server-authoritative).
ObbyRemote.OnServerEvent:Connect(function(player, action)
	if not currentStage[player] then return end
	if action == "restart" then
		resetPlayer(player)
	elseif action == "continue" then
		-- Client can't skip the obby. The only real progression is a Finish touch.
		return
	end
end)

-- If a stage is added at runtime, pick it up. Harmless in a starter; the runner
-- normally adds all stages before pressing Play.
StagesFolder.ChildAdded:Connect(function(child)
	task.wait()
	stages = findStages()
	if child:IsA("Model") and child:FindFirstChild("Begin") and child:FindFirstChild("Finish") then
		attachBegin(child)
		attachFinish(child)
	end
end)
