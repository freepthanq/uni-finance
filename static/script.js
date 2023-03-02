function ajax_request(argument) {
    var aj = new XMLHttpRequest ();
    aj.onreadystatechange = function() {
        if (aj.readyState == 4 && aj.status == 200)
        return "OK"
    };

    aj.open("GET", "/quote", true);
    aj.send();
}
