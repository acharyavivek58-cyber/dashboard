-- StarterGui.WinGui.WinFrame.LocalScript
-- Win screen for the obby starter. The server drives show/hide via the
-- ReplicatedStorage.ObbyRemote RemoteEvent, so the win is server-authoritative.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local player = Players.LocalPlayer
local ObbyRemote = ReplicatedStorage:WaitForChild("ObbyRemote")

local gui = script.Parent
local frame = gui:FindFirstChildWhichIsA("Frame")
if not frame then
	warn("WinGui LocalScript: no Frame found under WinGui")
	return
end

local titleLabel = frame:FindFirstChild("TitleLabel")
local continueBtn = frame:FindFirstChild("ContinueButton")
local restartBtn = frame:FindFirstChild("RestartButton")

local function show(title)
	frame.Visible = true
	if titleLabel and typeof(title) == "string" then
		titleLabel.Text = title
	end
end

local function hide()
	frame.Visible = false
end

if continueBtn and continueBtn:IsA("TextButton") then
	continueBtn.MouseButton1Click:Connect(function()
		ObbyRemote:FireServer("continue")
		hide()
	end)
end

if restartBtn and restartBtn:IsA("TextButton") then
	restartBtn.MouseButton1Click:Connect(function()
		ObbyRemote:FireServer("restart")
		hide()
	end)
end

ObbyRemote.OnClientEvent:Connect(function(action, stageName)
	if action == "showwin" then
		show("Stage Complete\n" .. (stageName or ""))
	elseif action == "hidewin" then
		hide()
	end
end)

hide()
