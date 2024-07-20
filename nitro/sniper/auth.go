package main

import (
	"bytes"
	"crypto"
	"crypto/aes"
	"crypto/cipher"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"encoding/pem"
	"fmt"
	"strings"
	"io/ioutil"
	"math/big"
	"math/rand"
	"os"
	"os/exec"
	"runtime"
	"time"

	"github.com/fasthttp/websocket"
)

type DiffieHellman struct {
	p *big.Int
	g int64
	a *big.Int
}

func NewDiffieHellman() *DiffieHellman {
	p, _ := new(big.Int).SetString("FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7EDEE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F83655D23DCA3AD961C62F356208552BB9ED529077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3BE39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF6955817183995497CEA956AE515D2261898FA051015728E5A8AACAA68FFFFFFFFFFFFFFFF", 16)
	return &DiffieHellman{
		p: p,
		g: 2,
		a: randomBigInt(),
	}
}

func (d *DiffieHellman) GetPrivateKey() *big.Int {
	return d.a
}

func (d *DiffieHellman) GeneratePublicKey() *big.Int {
	return new(big.Int).Exp(big.NewInt(d.g), d.a, d.p)
}

func (d *DiffieHellman) CheckOtherPublicKey(otherContribution *big.Int) bool {
	two := big.NewInt(2)
	if otherContribution.Cmp(two) >= 0 && otherContribution.Cmp(new(big.Int).Sub(d.p, two)) <= 0 {
		if new(big.Int).Exp(otherContribution, new(big.Int).Div(new(big.Int).Sub(d.p, big.NewInt(1)), big.NewInt(2)), d.p).Cmp(big.NewInt(1)) == 0 {
			return true
		}
	}
	return false
}

func (d *DiffieHellman) GenerateSharedKey(otherContribution *big.Int) ([]byte, error) {
	if d.CheckOtherPublicKey(otherContribution) {
		sharedKey := new(big.Int).Exp(otherContribution, d.a, d.p)
		sha256Hash := sha256.Sum256([]byte(sharedKey.String()))
		return sha256Hash[:], nil
	}
	return []byte("0"), fmt.Errorf("bad public key from other party")
}

func randomBigInt() *big.Int {
	randomBytes := make([]byte, 32)
	_, err := rand.Read(randomBytes)
	if err != nil {
		LogError(err.Error())
		os.Exit(1)
		panic(".")
	}
	return new(big.Int).SetBytes(randomBytes)
}

func verifySignature(text string, b64Signature string, certificate *rsa.PublicKey) bool {
	signature, _ := base64.StdEncoding.DecodeString(b64Signature)
	hashed := sha256.Sum256([]byte(text))

	err := rsa.VerifyPKCS1v15(certificate, crypto.SHA256, hashed[:], signature)
	return err == nil
}

func LoadRSAPublicKey(base64PEM string) (*rsa.PublicKey, error) {
	pemBytes, err := base64.StdEncoding.DecodeString(base64PEM)
	if err != nil {
		return nil, err
	}
	block, _ := pem.Decode(pemBytes)
	if block == nil {
		return nil, fmt.Errorf("failed to parse block")
	}
	pubKey, err := x509.ParsePKIXPublicKey(block.Bytes)
	if err != nil {
		return nil, err
	}

	rsaKey, ok := pubKey.(*rsa.PublicKey)
	if !ok {
		return nil, fmt.Errorf("got unexpected type: %T", rsaKey)
	}

	return rsaKey, nil
}

func runCommand(command string) (string) {
	var cmd *exec.Cmd
	if runtime.GOOS == "windows" {
		cmd = exec.Command("cmd", "/C", command)
	} else {
		cmd = exec.Command("sh", "-c", command)
	}

	var output bytes.Buffer
	cmd.Stdout = &output

	cmd.Run()
	// LogDebug(strings.TrimSpace(output.String()))
	return strings.TrimSpace(output.String())
}

type AuthServerHello struct {
	ServerPubKey    string `json:"a"`
	ServerSignature string `json:"b"`
}

type AuthClientHello struct {
	ClientPubKey    string `json:"a"`
	ClientRandomEnc string `json:"b"`
	ClientRandom    string `json:"c"`
}

type AuthClientIdentifyData struct {
	Hwid    string `json:"hwid"`
	License string `json:"license"`
	Program string `json:"program"`
	Version string `json:"version"`
}

type AuthClientIdentify struct {
	Op   string                 `json:"op"`
	Data AuthClientIdentifyData `json:"d"`
}

type AuthServerIdentify struct {
	Op          string `json:"op"`
	Status      string `json:"status"`
	Message     string `json:"message"`
	APIEndpoint string `json:"apiendpoint"`
	Expire		int	   `json:"expire"`
}

func Encrypt(plaintext []byte, key []byte) (string, error) {
	block, err := aes.NewCipher(key)
	if err != nil {
		return "", err
	}

	// Pad the plaintext to a multiple of the block size
	padding := block.BlockSize() - len(plaintext)%block.BlockSize()
	plaintext = append([]byte(plaintext), bytes.Repeat([]byte{byte(0)}, padding)...)

	// Generate a random IV
	iv := make([]byte, block.BlockSize())
	rand.Seed(time.Now().UnixNano())
	rand.Read(iv)

	// Encrypt the message using AES CBC
	mode := cipher.NewCBCEncrypter(block, iv)
	ciphertext := make([]byte, len(plaintext))
	mode.CryptBlocks(ciphertext, plaintext)

	// Return the ciphertext as a hex-encoded string with the IV prepended
	return hex.EncodeToString(append(iv, ciphertext...)), nil
}

// Decrypt decrypts a message using AES CBC and a shared secret.
func Decrypt(ciphertext string, sharedSecret []byte) ([]byte, error) {
	iv, err := hex.DecodeString(ciphertext[:32]) // extract the IV from the first 32 hex chars
	if err != nil {
		return nil, fmt.Errorf("error decoding IV: %s", err)
	}

	cipherData, err := hex.DecodeString(ciphertext[32:]) // extract the cipher data from the remaining hex chars
	if err != nil {
		return nil, fmt.Errorf("error decoding cipher data: %s", err)
	}

	block, err := aes.NewCipher(sharedSecret) // create a new AES cipher with the shared secret
	if err != nil {
		return nil, fmt.Errorf("error creating cipher: %s", err)
	}

	mode := cipher.NewCBCDecrypter(block, iv) // create a new CBC mode decrypter

	// decrypt the cipher data
	plaintext := make([]byte, len(cipherData))
	mode.CryptBlocks(plaintext, cipherData)

	plaintext = bytes.TrimRight(plaintext, string(0))

	return plaintext, nil
}

func StringToSHA256Hash(s string) string {
	hash := sha256.Sum256([]byte(s))
	return hex.EncodeToString(hash[:])
}

func GenerateRandomBytes(n int) (string, error) {
	bytes := make([]byte, n)
	if _, err := rand.Read(bytes); err != nil {
		return "", err
	}
	return hex.EncodeToString(bytes), nil
}

func BytesToSHA256Hash(input []byte) string {
	hash := sha256.Sum256(input)
	return hex.EncodeToString(hash[:])
}

func RunAuth() AuthServerIdentify {
	// get hwid
	hwid := StringToSHA256Hash(
		// universal
		fmt.Sprint(runtime.NumCPU()) + 
		// BSD
		runCommand("cat /etc/hostid") + 
		runCommand("kenv -q smbios.system.uuid") + 
		// Linux
		runCommand("cat /var/lib/dbus/machine-id") + 
		runCommand("cat /etc/machine-id") + 
		// Mac OS
		runCommand("ioreg -rd1 -c IOPlatformExpertDevice | grep IOPlatformUUID") + 
		// Windows
		runCommand("reg query HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Cryptography /v MachineGuid") +
		runCommand("wmic csproduct get vendor, version, name, identifyingnumber, uuid, skunumber"),
	)

	LogInfo("<<HWID:>> " + hwid)

	// get license from file
	license, err := ioutil.ReadFile("license")
	if err != nil {
		LogError(err.Error())
		os.Exit(1)
		panic(".")
	}
	license_str := string(license)

	// decode certificate
	rsa_cert_str := "L" + "S0t" + "LS1C" + "RUdJTiBQV" + "UJMSU" + "MgS0V" + "ZLS0tLS0KTUlJQklqQU5CZ2txaGtpRz" + "l3MEJBUUVGQUFPQ0FROEFNSUlCQ2d" + "LQ0FRRUFubUhka0F6RGlJcGs3R0VnekdnMAptZ2th" + "VTZzQTJCNTV2RERYenpNNlBNdkFsRU41ZjhScWFTNmc2QkVZbDNSaGRGazBTdjZrTDZpbGM1dmRqUH" + "hLCk5ibnBNaW5PT3orTHRFeFl2e" + "GJXbnRNeTBGR2orcj" + "R4UTUrQ2gvK2pYRUlWSVYyL" + "3FxSmJ3NXBmNHdxVjN2NXMKWHkwbDN" + "5YTNWMEJEUUJGYXhmMENjQVNEVFJOblhZQ" + "WU2Y24xTmFZMlFCOXoxRFl" + "CZlNScnJOdVo2cUNxWldPbApO" + "cVNxZW1pS1ArNVg3Ukt3aU1DRkZ4Ulo2SmRnSDdjTkFSUUZza" + "m1UV2NaZ093R1hsZnlHS2g3WThhdXlKSXVPCkZRUW1XcnQ2bG1FSE" + "tzRjBTQXhqWmp5RGcvYkRkZVAxRGZlc" + "kNpcFlQdlZzcVlzdEZh" + "RW1Hb" + "W5YdmNEVncwV1oKalFJREFRQUIKLS0tLS1FTkQgUFVCTElDI" + "EtFWS0" + "tL" + "S" + "0" + "t"
	rand.Seed(time.Now().UnixNano())
	rsa_cert_bytes, err := base64.StdEncoding.DecodeString(rsa_cert_str)
	if err != nil {
		LogError(err.Error())
		os.Exit(1)
		panic(".")
	}

	conn, _, err := websocket.DefaultDialer.Dial("ws://localhost:8069/auth?h="+BytesToSHA256Hash(rsa_cert_bytes), nil)
	if err != nil {
		LogError(err.Error())
		os.Exit(1)
		panic(".")
	}
	defer conn.Close()

	err = conn.SetReadDeadline(time.Now().Add(5 * time.Second))
	if err != nil {
		LogError(err.Error())
		os.Exit(1)
		panic(".")
	}
	_, message, err := conn.ReadMessage()
	if err != nil {
		LogError(err.Error())
		os.Exit(1)
		panic(".")
	}

	var resp AuthServerHello
	err = json.Unmarshal(message, &resp)
	if err != nil {
		LogError(err.Error())
		os.Exit(1)
		panic(".")
	}

	cert, err := LoadRSAPublicKey(rsa_cert_str)
	if err != nil {
		LogError(err.Error())
		os.Exit(1)
		panic(".")
	}
	if !verifySignature(resp.ServerPubKey, resp.ServerSignature, cert) {
		panic("Client failed to verify server.")
	}

	// create DH keys + shared key
	dh := NewDiffieHellman()
	server_pub_int := new(big.Int)
	server_pub_int, ok := server_pub_int.SetString(resp.ServerPubKey, 10)
	if !ok {
		panic("parse int error")
	}
	shared_key, err := dh.GenerateSharedKey(server_pub_int)
	if err != nil {
		LogError(err.Error())
		os.Exit(1)
		panic(".")
	}

	// get nonce and encrypt
	rand_chars, err := GenerateRandomBytes(16)
	if err != nil {
		LogError(err.Error())
		os.Exit(1)
		panic(".")
	}
	rand_chars_enc, err := Encrypt([]byte(rand_chars), shared_key)
	if err != nil {
		LogError(err.Error())
		os.Exit(1)
		panic(".")
	}

	// send auth data
	msg := AuthClientHello{
		ClientPubKey:    dh.GeneratePublicKey().String(),
		ClientRandomEnc: rand_chars_enc,
		ClientRandom:    rand_chars,
	}
	err = conn.WriteJSON(msg)
	if err != nil {
		LogError(err.Error())
		os.Exit(1)
		panic(".")
	}

	// read server response if nonce was validated
	err = conn.SetReadDeadline(time.Now().Add(5 * time.Second))
	if err != nil {
		LogError(err.Error())
		os.Exit(1)
		panic(".")
	}
	_, confmessage, err := conn.ReadMessage()
	if err != nil {
		LogError(err.Error())
		os.Exit(1)
		panic(".")
	}
	if string(confmessage) == "0" {
		LogError("Failed to secure tunnel with authentication server.")
		os.Exit(1)
		panic(".")
	}

	// get auth data, encrypt, and send
	idmsg := AuthClientIdentify{
		Op: "auth",
		Data: AuthClientIdentifyData{
			Hwid:    hwid,
			License: license_str,
			Program: "sniper",
			Version: version,
		},
	}
	idmsg_bytes, err := json.Marshal(idmsg)
	if err != nil {
		LogError(err.Error())
		os.Exit(1)
		panic(".")
	}
	idmsg_enc, err := Encrypt(idmsg_bytes, shared_key)
	if err != nil {
		LogError(err.Error())
		os.Exit(1)
		panic(".")
	}
	err = conn.WriteMessage(websocket.TextMessage, []byte(idmsg_enc))
	if err != nil {
		LogError(err.Error())
		os.Exit(1)
		panic(".")
	}

	// receive server, decrypt
	err = conn.SetReadDeadline(time.Now().Add(5 * time.Second))
	if err != nil {
		LogError(err.Error())
		os.Exit(1)
		panic(".")
	}
	_, verifymessage, err := conn.ReadMessage()
	if err != nil {
		LogError(err.Error())
		os.Exit(1)
		panic(".")
	}
	verify_str, err := Decrypt(string(verifymessage), shared_key)
	if err != nil {
		LogError(err.Error())
		os.Exit(1)
		panic(".")
	}
	var srvresp AuthServerIdentify
	err = json.Unmarshal([]byte(verify_str), &srvresp)
	if err != nil {
		LogError(err.Error())
		os.Exit(1)
		panic(".")
	}

	// fail if auth bad
	if srvresp.Status != "success" {
		LogError("[AUTH] " + srvresp.Message)
		os.Exit(1)
		panic(".")
	}

	return srvresp
}
