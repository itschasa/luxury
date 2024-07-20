package main

import (
	"bufio"
	"fmt"
	"io/ioutil"
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"encoding/base64"
	"io"
	"os"
	"os/exec"
	"regexp"
	"runtime"
	"strconv"
	"strings"
	"os/signal"
	"time"
	"sync"

	"github.com/gookit/color"
	//"github.com/bwmarrin/discordgo"
)

var (
	version = "v2.1.0"

	stats_messages          = 0
	stats_invites           = 0
	stats_guilds            = make(map[string]int)
	stats_alts              = 0
	stats_alts_online       = make(map[string]int)
	stats_attempts          = 0
	stats_hits              = 0
	guild_rate_limit        = make(map[string]int)
	guild_stack_map         = make(map[string]int)
	guild_stack_last_update = time.Now()
	global_queue_amount     = []int{}
	global_queue            = []string{}

	boot_time = time.Now().Unix()

	local_api_endpoint = ""

	instance_id = ""

	regex_invite = regexp.MustCompile("(discord.gg/invite|discord.gg|discord.com/invite)/([a-zA-Z0-9]+)")
)

func removeStringFromSlice(str string, slice []string) []string {
	for i := 0; i < len(slice); i++ {
		if slice[i] == str {
			// remove the element by copying the last element over it
			slice[i] = slice[len(slice)-1]
			slice = slice[:len(slice)-1]
			i-- // decrement i since we've shifted the last element to this position
		}
	}
	return slice
}

func checkDebugger() bool {
	reDebugger := regexp.MustCompile("fiddler|wireshark|telerik|debugger|charles|smartsniff|networkminer")
	if runtime.GOOS == "windows" {
		out, _ := exec.Command("cmd", "/C", "tasklist").Output()
		if reDebugger.Match([]byte(strings.ToLower(string(out)))) {
			return true
		}
	} else {
		out, _ := exec.Command("ps", "aux").Output()
		if reDebugger.Match([]byte(strings.ToLower(string(out)))) {
			return true
		}
	}
	return false
}

func encrypt(key, plaintext string) (string) {
	block, err := aes.NewCipher([]byte(key))
	if err != nil {
		LogError("Error encrypting tokens: " + err.Error())
		return ""
	}

	// Create a new GCM cipher with the given key
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		LogError("Error encrypting tokens: " + err.Error())
		return ""
	}

	// Generate a random nonce (IV)
	nonce := make([]byte, gcm.NonceSize())
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		LogError("Error encrypting tokens: " + err.Error())
		return ""
	}

	// Encrypt the plaintext using the GCM cipher
	ciphertext := gcm.Seal(nonce, nonce, []byte(plaintext), nil)

	// Return the base64-encoded ciphertext
	return base64.StdEncoding.EncodeToString(ciphertext)
}

func decrypt(key, ciphertext string) (string) {
	block, err := aes.NewCipher([]byte(key))
	if err != nil {
		LogError("Error decrypting tokens: " + err.Error())
		return ""
	}

	// Create a new GCM cipher with the given key
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		LogError("Error decrypting tokens: " + err.Error())
		return ""
	}

	// Decode the base64-encoded ciphertext
	decodedCiphertext, err := base64.StdEncoding.DecodeString(ciphertext)
	if err != nil {
		LogError("Error decrypting tokens: " + err.Error())
		return ""
	}

	// Split the nonce and the actual ciphertext
	nonceSize := gcm.NonceSize()
	nonce, ciphertext := decodedCiphertext[:nonceSize], string(decodedCiphertext)[nonceSize:]

	// Decrypt the ciphertext using the GCM cipher
	plaintext, err := gcm.Open(nil, nonce, []byte(ciphertext), nil)
	if err != nil {
		LogError("Error decrypting tokens: " + err.Error())
		return ""
	}

	// Return the decrypted plaintext
	return string(plaintext)
}


func readTokens() ([]string, error) {
	file, err := os.Open("tokens.txt")
	if err != nil {
		return nil, err
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	var tokens []string
	for scanner.Scan() {
		token := scanner.Text()
		if len(token) > 0 {
			tokens = append(tokens, token)
		}
	}

	if err := scanner.Err(); err != nil {
		return nil, err
	}

	var decrypted_tokens []string

	for _, token := range tokens {
		if strings.Contains(token, "*enc*:") {
			_, cipher, _ := strings.Cut(token, "enc*:")
			decrypted_tokens = append(decrypted_tokens, decrypt("luxuryandchasaarethecutestcouple", cipher))
		} else {
			decrypted_tokens = append(decrypted_tokens, token)
		}
	}

	return decrypted_tokens, nil
}

func writeEncryptedTokens(tokens []string) {
	file, err := os.OpenFile("enc_tokens.txt", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		LogError("Failed to open enc_tokens.txt: " + err.Error())
		return
	}
	for _, match := range tokens {
		_, _ = file.WriteString("*enc*:" + encrypt("luxuryandchasaarethecutestcouple", match) + "\n")
	}
	file.Close()
}

func addCommasToInt(n int) string {
	in := strconv.Itoa(n)
	numOfDigits := len(in)
	if n < 0 {
		numOfDigits-- // First character is the - sign (not a digit)
	}
	numOfCommas := (numOfDigits - 1) / 3

	out := make([]byte, len(in)+numOfCommas)
	if n < 0 {
		in, out[0] = in[1:], '-'
	}

	for i, j, k := len(in)-1, len(out)-1, 0; ; i, j = i-1, j-1 {
		out[j] = in[i]
		if i == 0 {
			return string(out)
		}
		if k++; k == 3 {
			j, k = j-1, 0
			out[j] = ','
		}
	}
}

func AntiSpamTimer() {
	for {
		time.Sleep(time.Minute)
		guild_rate_limit = make(map[string]int)
	}	
}

func GuildStackTimer() {
	for {
		time.Sleep(time.Minute)
		if time.Since(guild_stack_last_update).Seconds() > 5 { // just to make sure it doesnt get overriden whilst theres a claim-chain
			guild_stack_map = make(map[string]int)
		} else {
			time.Sleep(10 * time.Second)
			guild_stack_map = make(map[string]int)
		}
	}
}

func main() {
	color.Println(color_main + `
  _______                ____________        
   ___  / ____  _____  ____(_)__  __/____  __
   __  /  _  / / / / |/ / / /__  /_ __  / / /
   _  /___/ /_/ /  >  <  / / _  __/ _  /_/ / 
   /_____/\__,_/ /_/|_| /_/  /_/    _\__, /  
                                    /____/   
</>	`)
	LogInfo("<<Version:>> " + version)

	if checkDebugger() {
		LogError("Disable any debugging or proxy software (wireshark, etc), and retry.")
		os.Exit(1)
		panic(".")
	} else {

		LogInfo("Logging in...")
		//auth_obj := RunAuth()
		auth_obj := AuthServerIdentify{
			Expire:      0,
			Status:      "success",
			APIEndpoint: "",
			Op:          "",
			Message:     "",
		}
		local_api_endpoint = auth_obj.APIEndpoint
		expires := auth_obj.Expire

		if auth_obj.Status == "success" {
			LogSuccess("Authenticated!\n")

			// pre-make tls + http2 connection, to prevent high delay on first request
			EstablishConnection("Established", ".\n", "", false)
			EstablishConnection("Tested", ">>.\n", "<<", false)

			file_innit, err := ioutil.ReadFile("instance_id")
			if err != nil {
				LogError(err.Error())
				os.Exit(1)
				panic(".")
			}
			instance_id = string(file_innit)
			LogInfo("<<InstanceID:>> " + instance_id)

			start_time := time.Now()
			api_check := LuxAPIUpdate()
			duration_to_connect := time.Since(start_time)

			if api_check == "" {
				LogSuccess("Connected to LuxuryNitro API in <<" + duration_to_connect.String() + ">>!\n")
			} else {
				LogError(api_check)
				os.Exit(1)
				panic(".")
			}

			go LocalAPILoop()

			go func() {
				for {
					time.Sleep(time.Second * 30)
					// runtime.GC()
					if time.Now().Unix() > int64(expires) && expires != 0 {
						LogError("Your license has expired. Contact us to renew it.")
						os.Exit(1)
						panic(".")
					}
				}
			}()

			go func() {
				for {
					time.Sleep(time.Second * 10)
					PerformPingPong()
				}
			}()

			tokens, err := readTokens()
			writeEncryptedTokens(tokens)
			if err != nil {
				LogError("Failed to load tokens.txt: " + err.Error())

			} else {
				stats_alts = len(tokens)
				LogInfo("Loaded " + fmt.Sprint(stats_alts) + " tokens from file.")
				LogInfo("Booting up...\n")
				boot_time = time.Now().Unix()

				go AntiSpamTimer()

				go GuildStackTimer()

				go func() {
					for _, token := range tokens {
						go StartToken(token)
						time.Sleep(time.Millisecond * 500)
					}
				}()

				go func() {
					for {
						for _, spinner := range []string{" ", ".", "o", "O", "*", " "} {
							LogLoop(spinner)
							time.Sleep(time.Millisecond * 150)
						}
					}
				}()

				go func() {
					sigchan := make(chan os.Signal)
					signal.Notify(sigchan, os.Interrupt)
					<-sigchan
					os.Exit(0)
					panic("exiting program")
				}()

				// keeps program running
				var wg sync.WaitGroup
				wg.Add(1)
				wg.Wait()
			}

		} else {
			os.Exit(1)
			panic(".")
		}
	}
}
