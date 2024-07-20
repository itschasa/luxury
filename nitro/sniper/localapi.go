package main

import (
	"bytes"
	"fmt"
	"crypto/tls"
	"io/ioutil"
	"net"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/andersfylling/disgord"
	jsoniter "github.com/json-iterator/go"
)

var (
	claim_token = ""

	snipe_headers = http.Header{
		"Content-Type":  {"application/json"},
		"Authorization": {claim_token},
		"User-Agent":    {"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"},
	}

	enc_k = []byte("6" + "fbaaa" + "659de" + "58e1a" + "8ca" + "6f5" + "43a9" + "ddfa" + "11f14c" + "b24" + "329" + "d52" + "6952" + "dbf" + "a6406" + "a247" + "c7" + "2")

	localclient = &http.Client{
		Transport: &http.Transport{
			TLSClientConfig:     &tls.Config{InsecureSkipVerify: true},
			DisableKeepAlives:   false,
			MaxIdleConnsPerHost: 1000,
			ForceAttemptHTTP2:   true,
			DisableCompression:  true,
			IdleConnTimeout:     0,
			MaxIdleConns:        0,
			MaxConnsPerHost:     0,
			DialContext:         (&net.Dialer{KeepAlive: 30 * time.Second}).DialContext,
		},
		Timeout: 20 * time.Second,
	}

	promo_code_mutex = &sync.Mutex{}
	fastjson         = jsoniter.ConfigFastest
)

// update api on snipe hit/fail
func SnipeNotification(code string, message *disgord.Message, response_body string, start_time time.Time, end_time time.Time, sniper_user disgord.Session, status_code int, guild_id string, token_used string) {
	timestamp := message.Timestamp.Time

	snipe_time_recv := end_time.Sub(start_time).String()
	snipe_time_sent := end_time.Sub(timestamp).String()
	// LogDebug("recv: "+ snipe_time_recv + " sent: " + snipe_time_sent)

	success := 0
	var reason string

	if strings.HasPrefix(response_body, "!") {
		// sniper request error
		reason = strings.ReplaceAll(response_body, "!", "")
	} else {
		if (strings.Contains(strings.ToLower(response_body), `"consumed":true`) || strings.Contains(strings.ToLower(response_body), `"consumed": true`)) && status_code == 200 {
			success = 1
			splits := strings.Split(strings.Split(response_body, `subscription_plan`)[1], `name": "`)
			if len(splits) > 1 {
				reason = strings.Split(splits[1], `"`)[0]
			} else {
				reason = strings.Split(strings.Split(strings.Split(response_body, `subscription_plan`)[1], `name":"`)[1], `"`)[0]
			}

		} else if status_code == 429 {
			reason = "Rate Limited"
			success = 3

		} else if len(strings.Split(response_body, `{"message": "`)) > 1 {
			reason = strings.ReplaceAll(strings.Split(strings.Split(response_body, `{"message": "`)[1], `"`)[0], ".", "")

			// promo gift
			if strings.Contains(reason, "Payment source required to redeem") {
				success = 2
				snipe_mutex.Unlock()
				promo_code_mutex.Lock()
				file, err := os.OpenFile("promos.txt", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
				if err != nil {
					LogError("Failed to save to promos.txt: " + err.Error())
				} else {
					_, _ = file.WriteString(code + "\n")
					file.Close()
				}
				promo_code_mutex.Unlock()
			}

		} else {
			// shit blew up :kek:
			reason = response_body
		}
	}

	// success = 1
	// reason = "Nitro Monthly"

	if success == 1 {
		stats_hits += 1
		guild_stack_map[guild_id] += 1
		guild_stack_last_update = time.Now()
		HandleQueueShift(reason)
		LogSuccessBold("Sniped <<" + reason + ">> in <<" + snipe_time_recv + ">>:")
		LogSuccess("  Code: " + code + " | Sniper: " + GetTokenFromSession(sniper_user) + " | Author: " + message.Author.Username + "#" + message.Author.Discriminator.String() + " | TrueTime: " + snipe_time_sent)
		LuxAPIOnHit(reason, snipe_time_recv, token_used)

	} else if success == 0 {
		snipe_mutex.Unlock()
		guild_rate_limit[guild_id] += 1
		LogWarn("Miss for <<" + reason + ">> on " + GetTokenFromSession(sniper_user) + " (<<" + snipe_time_recv + ">>/<<" + snipe_time_sent + ">>) (" + code + ")") // + "/" + snipe_time_sent + ")")
	} else if success == 2 {
		LogInfo("Found Promo Code <<" + code + ">> on " + GetTokenFromSession(sniper_user) + " (<<" + snipe_time_recv+ ">>/<<" + snipe_time_sent + ">>)") // + "/" + snipe_time_sent + ")")
	} else if success == 3 {
		snipe_mutex.Unlock()
		if guild_stack_map[guild_id] > 0 {
			LuxAPIOnRateLimit(guild_id, code, sniper_user, message, start_time)
		} else {
			LogWarn("Miss for <<" + reason + ">> on " + GetTokenFromSession(sniper_user) + " (<<" + snipe_time_recv + ">>/<<" + snipe_time_sent + ">>) (" + code + ")")
		}
	}
}

func HandleQueueShift(nitro_type string) {
	if strings.Contains(nitro_type, "Boost") {
		// boost nitro claimed
		tmp_hold := global_queue_amount[0]
		tmp_hold2 := global_queue[0]
		if tmp_hold - 1 > 0 && global_queue_amount[0] != -999 { // if they have nitro to redeem still, put them at back
			global_queue_amount = append(global_queue_amount[1:], tmp_hold - 1)
			global_queue = append(global_queue[1:], tmp_hold2)
		} else if global_queue_amount[0] != -999 { // no credits left, remove from queue
			global_queue_amount = global_queue_amount[1:]
			global_queue = global_queue[1:]
		}
	} else {
		if global_queue_amount[0] - 1 < 1 && global_queue_amount[0] != -999 { // if they out of credits, remove from queue
			global_queue_amount = global_queue_amount[1:]
			global_queue = global_queue[1:]
		}
	}
	claim_token = global_queue[0]
	snipe_headers = http.Header{
		"Content-Type":  {"application/json"},
		"Authorization": {claim_token},
		"User-Agent":    {"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"},
	}

	defer func() {
        if r := recover(); r != nil {
            LogWarn("Recovered from " + fmt.Sprint(r))
        }
    }()
	snipe_mutex.Unlock()
}

type WebServerResponseError struct {
	Err   bool   `json:"error"`
	Msg   string `json:"message"`
}

type WebServerResponse struct {
	Err   		bool     `json:"error"`
	Msg   		string   `json:"message"`
	Token 		string   `json:"token"`
	QueueTokens []string `json:"queue_tokens"`
	QueueAmount []int    `json:"queue_amount"`
	HitMsg		[]string `json:"hit_msg"`
}

type RateLimitData struct {
	guild_id string
	code string
	sniper_user disgord.Session
	message *disgord.Message
}

// func to get token from api
func LuxAPIUpdate() string {
	Xalts := fmt.Sprint(stats_alts)
	counter := 0
	for _, v := range stats_guilds {
		counter += v
	}
	Xtotal_servers := fmt.Sprint(counter)
	return LuxAPIDoReq(`{"type": 0, "alts": "` + Xalts + `", "servers": "` + Xtotal_servers + `"}`)
}

func LuxAPIOnHit(nitro string, timing string, token_used string) string {
	return LuxAPIDoReq(`{"type": 1, "token": "` + token_used + `", "snipe": "` + nitro + `", "time": "` + timing + `"}`)
}

func LuxAPIOnRateLimit(guild_id string, code string, sniper_user disgord.Session, message *disgord.Message, start_time time.Time) string {
	return LuxAPIDoReq(`{"type": 2, "code": "` + code + `", "time": ` + fmt.Sprint(start_time.UnixMilli()) + `}`,
		RateLimitData{
			guild_id: guild_id,
			code: code,
			sniper_user: sniper_user,
			message: message,
		},
	)
}

func LuxAPIDoReq(data string, rate_limit_data ...RateLimitData) string {
	var request, requestErr = http.NewRequest("POST", "https://dash.luxurynitro.com/api/v1/sniper", bytes.NewBuffer([]byte(data)))

	if requestErr != nil {
		LogError("Failed to build request for LuxuryAPI: " + requestErr.Error())
		return ""
	}

	request.Close = false
	request.Header = http.Header{
		"Content-Type": {"application/json"},
		"Connection": {"keep-alive"},
		"Authorization": {"***"},
		"X-Instance-ID": {instance_id},
	}

	var response, responseErr = localclient.Do(request)

	if responseErr != nil {
		LogError("Failed to do request for LuxuryAPI: " + responseErr.Error())
		return ""
	}

	defer response.Body.Close()
	bodyBytes, err := ioutil.ReadAll(response.Body)
	if err != nil {
		LogError("Failed to decode response from LuxuryAPI: " + err.Error())
		return ""
	}
	bodyString := string(bodyBytes)

	if response.StatusCode != 200 {
		bodyData := WebServerResponseError{}
		err := fastjson.Unmarshal([]byte(bodyString), &bodyData)
		if err != nil {
			LogError("Error from Web Server: HTTP " + fmt.Sprint(response.StatusCode))
		} else {
			LogError("Error from Web Server: " + fmt.Sprint(bodyData.Err))
		}
		return fmt.Sprint(response.StatusCode)
	
	} else {
		bodyData := WebServerResponse{}
		err := fastjson.Unmarshal(bodyBytes, &bodyData)
		if err != nil {
			LogError("Error unmarshelling data: " + fmt.Sprint(bodyData.Err))
			return ""
		}
		
		snipe_mutex.Lock()
		global_queue = bodyData.QueueTokens
		global_queue_amount = bodyData.QueueAmount
		
		claim_token = bodyData.QueueTokens[0]
		snipe_headers = http.Header{
			"Content-Type":  {"application/json"},
			"Authorization": {claim_token},
			"User-Agent":    {"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"},
		}
		snipe_mutex.Unlock()
		
		if len(bodyData.HitMsg) > 0 {
			tm, err := time.ParseDuration(bodyData.HitMsg[2] + "s")
			var tm_str string
			if err != nil {
				tm_str = bodyData.HitMsg[2] + "s"
			} else {
				tm_str = tm.String()
			}
			if bodyData.HitMsg[0] == "1" {
				LogSuccessBold("Sniped <<" + bodyData.HitMsg[1] + ">> in <<" + tm_str + ">> (RateLimitBypass):")
				LogSuccess("  Code: " + rate_limit_data[0].code + " | Sniper: " + GetTokenFromSession(rate_limit_data[0].sniper_user) + " | Author: " + rate_limit_data[0].message.Author.Username + "#" + rate_limit_data[0].message.Author.Discriminator.String())
			} else {
				LogWarn("Miss for <<" + bodyData.HitMsg[1] + ">> (RateLimitBypass) on " + GetTokenFromSession(rate_limit_data[0].sniper_user) + " (<<" + tm_str + ">>) (" + rate_limit_data[0].code + ")")
			}
			
		}
		return ""
	}
}

func LocalAPIUpdate() {}

// loop that runs /\ every 5-ish seconds
func LocalAPILoop() {
	for {
		LuxAPIUpdate()
		time.Sleep(time.Second * 5)
	}
}
