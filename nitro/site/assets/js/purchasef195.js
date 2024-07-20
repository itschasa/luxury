$(function () {
    let activeForm;

    $('button[name="purchaseButton"]').on('click', function () {
        activeForm = $(this).parent('form');
    });

    $('#continue').on('click', function () {
        activeForm.submit();
    });
});