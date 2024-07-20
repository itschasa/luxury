package main

import (
	"bytes"
	"crypto/tls"
	"io/ioutil"
	"net"
	"net/http"
	"net/http/httptrace"
	"os"
	"strings"
	"sync"
	"time"
	"fmt"

	"github.com/andersfylling/disgord"
)

var client = &http.Client{
	Transport: &http.Transport{
		TLSClientConfig:     &tls.Config{InsecureSkipVerify: true},
		DisableKeepAlives:   false,
		MaxIdleConnsPerHost: 1000,
		ForceAttemptHTTP2:   true,
		DisableCompression:  true,
		IdleConnTimeout:     0,
		MaxIdleConns:        0,
		MaxConnsPerHost:     0,
		DialContext:         (&net.Dialer{KeepAlive: 9 * time.Second}).DialContext,
	},
	Timeout: 20 * time.Second,
}
var snipe_mutex = &sync.Mutex{}

func EstablishConnection(iter string, end string, pre string, silent bool) {
	start := time.Now()
	var request, requestErr = http.NewRequest("POST", "https://discord.com/api/v9/auth/location-metadata", bytes.NewBuffer([]byte(`{}`)))
	if requestErr != nil {
		LogError("Failed to build request for <<Connect Test>>")
		os.Exit(1)
		panic(".")
	}

	request.Header = snipe_headers
	request.Close = false

	var connect, dns, tlsHandshake time.Time

	trace := &httptrace.ClientTrace{
		DNSStart: func(dsi httptrace.DNSStartInfo) { dns = time.Now() },
		DNSDone: func(ddi httptrace.DNSDoneInfo) {
			LogDebug("DNS Done: " + time.Since(dns).String())
		},

		ConnectStart: func(network, addr string) { connect = time.Now() },
		ConnectDone: func(network, addr string, err error) {
			LogDebug("Connect time: " + time.Since(connect).String())
		},

		TLSHandshakeStart: func() { tlsHandshake = time.Now() },
		TLSHandshakeDone: func(cs tls.ConnectionState, err error) {
			LogDebug("TLS Handshake: " + time.Since(tlsHandshake).String())
		},

		GotFirstResponseByte: func() {
			LogDebug("TTFB: " + time.Since(start).String())
		},
	}

	request = request.WithContext(httptrace.WithClientTrace(request.Context(), trace))

	var response, responseErr = client.Transport.RoundTrip(request)
	defer response.Body.Close()

	time_taken := time.Since(start).String()

	if responseErr != nil {
		LogError("Failed to do request for <<Connect Test>>")
		os.Exit(1)
		panic(".")
	}

	ioutil.ReadAll(response.Body)

	LogSuccess(iter + " connection with the Discord API in " + pre + time_taken + end)
}

func PerformPingPong() {
	defer func() {
        if r := recover(); r != nil {
            LogWarn("Recovered from " + fmt.Sprint(r))
        }
    }()
	
	var request, requestErr = http.NewRequest("GET", "https://discord.com/api/v9/auth/location-metadata", bytes.NewBuffer([]byte(``)))
	if requestErr != nil {
		return
	}
	request.Close = false
	
	var response, _ = client.Do(request)
	defer response.Body.Close()
}

func SnipeNitro(code string, start time.Time, message_data *disgord.Message, sniper_user disgord.Session, guild_id string) {
	var request, requestErr = http.NewRequest("POST", "https://discord.com/api/v9/entitlements/gift-codes/"+code+"/redeem", bytes.NewBuffer([]byte(`{}`)))

	if requestErr != nil {
		LogError("Failed to build request for nitro code <<" + code + ">>")
		SnipeNotification(code, message_data, "!Error on building request", start, time.Now(), sniper_user, 0, "", "")
		return
	}

	request.Close = false
	
	snipe_mutex.Lock()
	
	request.Header = snipe_headers
	token_used := strings.Clone(claim_token)
	
	var response, responseErr = client.Do(request)
	end := time.Now()

	stats_attempts += 1

	if responseErr != nil {
		snipe_mutex.Unlock()
		LogError("Failed to do request for nitro code <<" + code + ">>")
		SnipeNotification(code, message_data, "!Error on doing request", start, end, sniper_user, 0, "", "")
		return
	}

	defer response.Body.Close()
	bodyBytes, _ := ioutil.ReadAll(response.Body)

	SnipeNotification(code, message_data, string(bodyBytes), start, end, sniper_user, response.StatusCode, guild_id, token_used)
}
