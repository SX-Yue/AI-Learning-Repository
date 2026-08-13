#  Force the PowerShell console to read and write in UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# 1. Setup the Headers
$headers = @{
    "Content-Type"  = "application/json; charset=utf-8"
    "Authorization" = "Bearer sk-50427a897ede494dbab32b6e7496425b" # Put your key here
}

# 2. Create an array to act as the AI's "Memory"
$chatHistory = @(
    @{ role = "system"; content = "You are a helpful assistant." }
)

Write-Host "Chat started! Type 'exit' to quit." -ForegroundColor Yellow

# 3. Start an infinite loop to keep the conversation going
while ($true) {
    
    # Get your input from the console
    $userInput = Read-Host -Prompt "`nYou"
    
    # If you type 'exit', break the loop and end the script
    if ($userInput -eq 'exit') { 
        Write-Host "Goodbye!" -ForegroundColor Yellow
        break 
    }

    # Add your new message to the chat history memory
    $chatHistory += @{ role = "user"; content = $userInput }

    # Build the payload dynamically (PowerShell converts this to JSON for us!)
    $bodyObject = @{
        model = "deepseek-v4-pro"
        messages = $chatHistory
        thinking = @{ type = "enabled" }
        reasoning_effort = "high"
        stream = $false
    }
    
    # Convert our PowerShell object into a JSON string
    $bodyJson = $bodyObject | ConvertTo-Json -Depth 10

    Write-Host "Thinking..." -ForegroundColor DarkGray

    # Send the request
    $response = Invoke-RestMethod -Uri "https://api.deepseek.com/chat/completions" `
                                  -Method Post `
                                  -Headers $headers `
                                  -Body $bodyJson

    # Extract the text from the response
    $aiText = $response.choices[0].message.content
    $aiThinking = $response.choices[0].message.reasoning_content

    # Print the AI's response
    Write-Host "`n--- AI Thinking ---" -ForegroundColor Cyan
    Write-Host $aiThinking
    Write-Host "`n--- AI Response ---" -ForegroundColor Green
    Write-Host $aiText

    # VERY IMPORTANT: Add the AI's response to the memory so it remembers this for next time!
    $chatHistory += @{ role = "assistant"; content = $aiText }
}