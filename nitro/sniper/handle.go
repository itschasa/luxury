package main

import (
	"context"
	"encoding/base64"
	"fmt"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/andersfylling/disgord"
)

var invite_file_mutex = &sync.Mutex{}
var nitroChecked = make(map[string]bool)
var tokenPrefixes = make(map[string]string)

// connects to discord with a token, and listens and processes new messages
func StartToken(token string) {	
	// login
	token_user := strings.Split(token, ".")[0]
	
	ctx := context.Background()
	client := disgord.New(disgord.Config{
		BotToken: token,
	})
	
	defer func(client *disgord.Client, ctx context.Context) {
		err := client.StayConnectedUntilInterrupted(ctx)
		if err != nil {
			LogError("Failed to login on " + token_user + ": " + strings.Split(err.Error(), "\n")[0])
		}
	}(client, ctx)

	// start listeners
	client.On(disgord.EvtMessageCreate, OnMessage)
	client.On(disgord.EvtReady, OnReady, &disgord.Ctrl{Runs: 1})
}

// handles new messages from gateway
func OnMessage(s disgord.Session, m *disgord.MessageCreate) {
	start := time.Now()
	
	text_contents := m.Message.Content
	for _, embedData := range m.Message.Embeds {
		text_contents += embedData.Title + embedData.Description + embedData.URL
		
		for _, embedFields := range embedData.Fields {
			text_contents += embedFields.Name + embedFields.Value
		}
	}
	
	ExtractNitroCodes(text_contents, start, m.Message, s)
	ExtractInviteCodes(text_contents)
	
	stats_messages += 1
}

// handles new connections to gateway (guild + online counter)
func OnReady(s disgord.Session, d *disgord.Ready) {
	stats_guilds[d.User.ID.String()] = len(d.Guilds)
	stats_alts_online[d.User.ID.String()] = 0
}

// processes a string (message content + embeds) and starts sniping // more complicated but about 20 times faster than regex (according to old dev)
func ExtractNitroCodes(input string, start_time time.Time, message_data *disgord.Message, sniper_user disgord.Session) {
	defer func() {
        if r := recover(); r != nil {
            LogWarn("Recovered from " + fmt.Sprint(r))
        }
    }()
	
	tempInput := strings.ToLower(input)
	for {
		start := strings.Index(tempInput, "/gifts/")
		code := ""
		if start != -1 {
			code = input[start+7:]
			for charIndex, char := range code {
				if char == ' ' || char == '/' || char == '\n' || char == '\r' || char == '\t' || charIndex == len(tempInput)-1 {
					code = code[:charIndex]
					break
				}
			}
		} else {
			start = strings.Index(tempInput, ".gift/")
			if start != -1 {
				code = input[start+6:]
				for charIndex, char := range code {
					if char == ' ' || char == '/' || char == '\n' || char == '\r' || char == '\t' || charIndex == len(tempInput)-1 {
						code = code[:charIndex]
						break
					}
				}
			} else {
				return
			}
		}

		input = input[start+6:]
		
		// the goroutines should prevent blocking of code (if there are multiple codes in msg)
		if !(len(code) < 16 || len(code) > 24) {
			if !nitroChecked[code] {
				guild_id := message_data.GuildID.String()
				if guild_rate_limit[guild_id] > 5 {
					go func() { 
						LogWarn("Miss for <<Anti-Spam>> (" + guild_id + ") on " + GetTokenFromSession(sniper_user) + " (" + code + ")")
					}()
				} else {
					go SnipeNitro(code, start_time, message_data, sniper_user, guild_id)
					nitroChecked[code] = true
				}
			} else {
				go func() { 
					LogWarn("Miss for <<Duplicate Code>> on " + GetTokenFromSession(sniper_user) + " (" + code + ")")
				}()
			}
		} else {
			go func() {
				LogWarn("Miss for <<Code Validation>> on " + GetTokenFromSession(sniper_user) + " (" + code + ")")
			}()
		}
		
		tempInput = tempInput[start+6:]
	}
}

// processes a string and extracts and saves all invite codes found (just raw code, no discord.gg/ or .gg/)
func ExtractInviteCodes(input string) {
	var matches []string
	submatches := regex_invite.FindAllStringSubmatch(input, -1)
	for _, submatch := range submatches {
		if len(submatch) > 1 {
			matches = append(matches, submatch[2])
		}
	}

	invite_file_mutex.Lock()
	file, err := os.OpenFile("invites.txt", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		LogError("Failed to open invites.txt: " + err.Error())
		return
	}
	for _, match := range matches {
		_, _ = file.WriteString(match + "\n")
		stats_invites += 1
	}
	file.Close()
	invite_file_mutex.Unlock()
}

func GetUserIDFromSession(s disgord.Session) string {
	user, err := s.GetCurrentUser(context.Background())
	if err != nil {
		LogError("ok genuinely wtf happened, failed to get UserID")
		return "[see above]"
	} else {
		return user.ID.String()
	}
}

func GetTokenFromSession(s disgord.Session) string {
	user_id := GetUserIDFromSession(s)
	token_prefix, ok := tokenPrefixes[user_id]
	if ok {
		return token_prefix
	} else {
		tokenPrefixes[user_id] = base64.RawStdEncoding.EncodeToString([]byte(user_id))
		return tokenPrefixes[user_id]
	}
	
}

func GetUsernameFromSession(s disgord.Session) string {
	user, err := s.GetCurrentUser(context.Background())
	if err != nil {
		LogError("ok genuinely wtf happened, failed to get User")
		return "[see above]"
	} else {
		return user.Username + "#" + user.Discriminator.String()
	}
}