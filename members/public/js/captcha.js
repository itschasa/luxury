var cjwt = ""

function getCaptcha() {
    if (turnstile.getResponse() == undefined) {
        return null
    }

    return {t: turnstile.getResponse(), j: cjwt}
}

window.onloadTurnstileCallback = function () {
    axios.get(`https://api-${window.location.host}/api/v1/captcha`)
        .then(response => {
            const responseData = response.data;
            cjwt = responseData.jwt
            
            turnstile.render('#captcha-div', {
                sitekey: responseData.key,
                theme: 'dark',
                callback: function(token) {
                    captchaSolved()
                },
                'retry-interval': 500,
                cData: responseData.cd

            });
        })
        .catch(error => {
            console.error(error)
        });
}