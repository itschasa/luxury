package main

import (
	"strings"
	"time"

	"github.com/gookit/color"
	"github.com/nathan-fiscaletti/consolesize-go"
)

var (
	color_main   = "<fg=b17aff>"
	color_info   = "<fg=5784e6>"
	color_gray   = "<fg=9c9c9c>"
	color_white  = "<white>"
	color_green  = "<fg=78eb85>"
	color_red    = "<fg=e84848>"
	color_yellow = "<fg=f7d154>"
)

func TimePrefix() string {
	return color_gray + time.Now().Format("15:04:05") + "</>"
}

func AddSpace(rawdata string, data string) {
	padding_data := ""
	width, _ := consolesize.GetConsoleSize()
	lines_width := width * (len(data) / width)
	if lines_width < 1 {
		lines_width = width
	}
	padding := lines_width - len(data)
	if padding > 0 {
		for i := 1; i <= padding; i++ {
			padding_data += " "
		}
	}

	color.Println("\r" + rawdata + padding_data)
}

func LogDebug(data string) {
	post_data := strings.ReplaceAll(strings.ReplaceAll(data, "<<", "</>"+color_main), ">>", "</>"+color_gray)
	AddSpace("\r"+color_gray+"></> "+TimePrefix()+color_gray+" |</> "+color_gray+post_data+"</>", "> 00:00:00 | "+strings.ReplaceAll(strings.ReplaceAll(data, ">>", ""), "<<", ""))
}

func LogInfo(data string) {
	post_data := strings.ReplaceAll(strings.ReplaceAll(data, "<<", "</>"+color_main), ">>", "</>"+color_gray)
	AddSpace("\r"+color_main+"></> "+TimePrefix()+color_main+" |</> "+color_gray+post_data+"</>", "> 00:00:00 | "+strings.ReplaceAll(strings.ReplaceAll(data, ">>", ""), "<<", ""))
}

func LogError(data string) {
	post_data := strings.ReplaceAll(strings.ReplaceAll(data, "<<", "</>"+color_main), ">>", "</>"+color_gray)
	AddSpace("\r"+color_red+"></> "+TimePrefix()+color_red+" |</> "+color_gray+post_data+"</>", "> 00:00:00 | "+strings.ReplaceAll(strings.ReplaceAll(data, ">>", ""), "<<", ""))
}

func LogWarn(data string) {
	post_data := strings.ReplaceAll(strings.ReplaceAll(data, "<<", "</>"+color_main), ">>", "</>"+color_gray)
	AddSpace("\r"+color_yellow+"></> "+TimePrefix()+color_yellow+" |</> "+color_gray+post_data+"</>", "> 00:00:00 | "+strings.ReplaceAll(strings.ReplaceAll(data, ">>", ""), "<<", ""))
}

func LogSuccess(data string) {
	post_data := strings.ReplaceAll(strings.ReplaceAll(data, "<<", "</>"+color_main), ">>", "</>"+color_gray)
	AddSpace("\r"+color_green+"></> "+TimePrefix()+color_green+" |</> "+color_gray+post_data+"</>", "> 00:00:00 | "+strings.ReplaceAll(strings.ReplaceAll(data, ">>", ""), "<<", ""))
}

func LogSuccessBold(data string) {
	post_data := strings.ReplaceAll(strings.ReplaceAll(data, "<<", "</>"+color_main), ">>", "</>"+color_white)
	AddSpace("\r"+color_green+"></> "+TimePrefix()+color_green+" |</> "+color_white+post_data+"</>", "> 00:00:00 | "+strings.ReplaceAll(strings.ReplaceAll(data, ">>", ""), "<<", ""))
}

func LogLoop(spinner string) {
	counter := 0
	for _, v := range stats_guilds {
		counter += v
	}
	data := addCommasToInt(counter) + " Guilds | " + 
		addCommasToInt(len(stats_alts_online)) + "/" + addCommasToInt(stats_alts) + " Alts | " + 
		addCommasToInt(stats_messages) + " Messages | " + 
		addCommasToInt(stats_invites) + " Invites | " + 
		addCommasToInt(stats_hits) + "/" + addCommasToInt(stats_attempts) + " Hits | " + 
		time.Unix(time.Now().Unix() - boot_time, 0).Format("15:04:05") + " Elapsed"
	
	color.Print("\r" + color_info + "></> " + TimePrefix() + color_info + " " + spinner + "</> " + color_gray + data + "</>")
}
