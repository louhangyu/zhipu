(function(exports) {
    var Status = function(options) {
        options = options || {};

        var self = this;

        this.container = $("#" + options.containerId);
        this.url = "/ctr/";
        this.spin = '<div class="spinner-border" role="status"><span class="sr-only">Loading...</span></div>';

        this.form1 = null;
        this.fieldset1 = null;
        this.h1 = null;
        this.btn = null;
        this.result = null;
        this.table = null;

        this.render = function() {
            var nodes = [
                "<h1 id='step1'>CTR <small></small></h1>",
                "<form method='get' id='form1'>",
                "  <fieldset>",
                "    <div class='form-group row'>",
                "        <label class='col-1 col-form-label'>开始日期</label>",
                "        <div class='col-3'>",
                "            <input type='date' class='form-control' name='start' required />",
                "        </div>",
                "        <label class='col-1 col-form-label'>结束日期</label>",
                "        <div class='col-3'>",
                "            <input type='date' class='form-control' name='end' required />",
                "        </div>",
                "        <div class='col-2'>",
                "            <button class='btn btn-primary'>查询</button>",
                "        </div>",
                "    </div>",
                "    <small id='tips' class='form-text'></small>",
                "  </fieldset>",
                "</form>",
                "<div id='result'>",
                "  <div id='chart'></div>",
                "  <div class='table-responsive'><table class='table table-bordered table-sm border-primary'></table></div>",
                "</div>"
            ];

            this.container.html(nodes.join(""));
            this.h1 = this.container.find("#step1");
            this.form1 = this.container.find("#form1");
            this.fieldset1 = this.form1.find("fieldset");
            this.btn = this.form1.find("button");
            this.result = this.container.find("#result");
            this.table = this.result.find("table");

            self.loadData();
        };

        this.loadData = function(start, end) {
            $.getJSON(self.url, {start: start, end: end}, function(resp) {
                console.debug("resp", resp);
                //render table
                var headers = [
                    "<tr>",
                    "    <th>Date</th>",
                    "    <th>group</th>",
                    "    <th>ctr</th>",
                    "    <th>show_per_ud</th>",
                    "    <th>click_per_ud</th>",
                    "    <th title='show ud count'>the number of show ud</th>",
                    "    <th>the number of show uid</th>",
                    "    <th>the number of show content</th>",
                    "    <th>show</th>",
                    "    <th>the number of click ud</th>",
                    "    <th>the number of click uid</th>",
                    "    <th>the number of click content</th>",
                    "    <th>click</th>",
                    "</tr>",
                ].join("");

                self.table.html(headers);
                for(var i=0; i<resp.data.length; i++) {
                    var item = resp.data[i].data;
                    var itemHtml = [
                        "<tr>",
                        "    <td rowspan=3>" + item.when + "</td>",
                        "    <td>All</td>",
                        "    <td class='table-success'>" + item.H.ctr.toFixed(4) + "</td>",
                        "    <td class='table-warning'>" + item.H.show_per_ud.toFixed(4) + "</td>",
                        "    <td class='table-primary'>" + item.H.click_per_ud.toFixed(4) + "</td>",
                        "    <td>" + item.H.ud + "</td>",
                        "    <td>" + item.H.uid + "</td>",
                        "    <td>" + item.H.pub + "</td>",
                        "    <td>" + item.H.show + "</td>",
                        "    <td>" + item.H.click_ud + "</td>",
                        "    <td>" + item.H.click_uid + "</td>",
                        "    <td>" + item.H.click_pub + "</td>",
                        "    <td>" + item.H.click + "</td>",
                        "</tr>",
                        "<tr>",
                        "    <td>A</td>",
                        "    <td>" + item.a.ctr.toFixed(4) + "</td>",
                        "    <td>" + item.a.show_per_ud.toFixed(4) + "</td>",
                        "    <td>" + item.a.click_per_ud.toFixed(4) + "</td>",
                        "    <td>" + item.a.ud + "</td>",
                        "    <td>" + item.a.uid + "</td>",
                        "    <td>" + item.a.pub + "</td>",
                        "    <td>" + item.a.show + "</td>",
                        "    <td>" + item.a.click_ud + "</td>",
                        "    <td>" + item.a.click_uid + "</td>",
                        "    <td>" + item.a.click_pub + "</td>",
                        "    <td>" + item.a.click + "</td>",
                        "</tr>",
                        "<tr>",
                        "    <td>B</td>",
                        "    <td>" + item.b.ctr.toFixed(4) + "</td>",
                        "    <td>" + item.b.show_per_ud.toFixed(4) + "</td>",
                        "    <td>" + item.b.click_per_ud.toFixed(4) + "</td>",
                        "    <td>" + item.b.ud + "</td>",
                        "    <td>" + item.b.uid + "</td>",
                        "    <td>" + item.b.pub + "</td>",
                        "    <td>" + item.b.show + "</td>",
                        "    <td>" + item.b.click_ud + "</td>",
                        "    <td>" + item.b.click_uid + "</td>",
                        "    <td>" + item.b.click_pub + "</td>",
                        "    <td>" + item.b.click + "</td>",
                        "</tr>",
                    ].join("");
                    self.table.append(itemHtml);
                }
            });
        };

        this.render();

        this.form1.submit(function(e) {
           e.preventDefault();

           var start = self.form1.find("input[name=start]").val();
           var end = self.form1.find("input[name=end]").val();

           self.loadData(start, end);
        });

    };

    exports.Status = Status;
})(window);