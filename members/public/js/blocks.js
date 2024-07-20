function formatUnixTimestamp(unixTimestamp) {
    const date = new Date(unixTimestamp);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');

    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
}

window.oauth_link = ''
axios({
    method: 'get',
    url: `https://api-${window.location.host}/api/v1/user`,
    headers: {
        authorization: localStorage.getItem("token")
    }
})
.then(function (response) {
    console.log(response);
    $('#stat_balance').text(`$${response.data.data.balance / 10000}`)
    $('#sellix-a').attr('data-sellix-custom-username', response.data.data.name)
    $('#sellix-a').attr('data-sellix-product', response.data.data.sellix_product_id)
    
    $('#info-username').val(response.data.data.name)
    $('#info-display').val(response.data.data.display_name)
    $('#info-email').val(response.data.data.email)
    $('#info-id').val(response.data.data.id)
    $('#info-created').val(formatUnixTimestamp(response.data.data.created_at))

    window.oauth_link = response.data.data.oauth_link

    if (response.data.data.ip_verification == true) {
        $('#ip-disable').show()
    } else if (response.data.data.ip_verification == false) {
        $('#ip-enable').show()
    }
})
.catch(function (error) {
    console.log(error);
    if (error.response.status == 401) {
        location.href = "https://" + location.host + "/login"
    }
});

axios({
    method: 'get',
    url: `https://api-${window.location.host}/api/v1/stock`,
    headers: {
        authorization: localStorage.getItem("token")
    }
})
.then(function (response) {
    console.log(response);
    for (const [key, value] of Object.entries(response.data.data)) {
        $(`#stock_${key}`).text(`${value}`)
    }
})
.catch(function (error) {
    console.log(error);
    if (error.response.status == 401) {
        location.href = "https://" + location.host + "/login"
    }
});

axios({
    method: 'get',
    url: `https://api-${window.location.host}/api/v1/user/orders`,
    headers: {
        authorization: localStorage.getItem("token")
    }
})
.then(function (response) {
    console.log(response);
    $('#stat_orders').text(`${response.data.data.length}`)
})
.catch(function (error) {
    console.log(error);
    if (error.response.status == 401) {
        location.href = "https://" + location.host + "/login"
    }
});