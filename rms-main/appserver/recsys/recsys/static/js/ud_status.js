(function(exports) {
    var UdStatus = function(options) {
        options = options || {};

        var self = this;

        this.container = $("#" + options.containerId);
        this.udSampleUrl = "/ud_sample/";
        this.udActionUrl = "/ud_action/";
        this.spin = '<div class="spinner-border" role="status"><span class="sr-only">Loading...</span></div>';

        this.form = null;
        this.fieldset = null;
        this.leftPanel = null;
        this.rightPanel = null;

        this.render = function() {
            var nodes = [
                "<h1 id='step1'>UD轨迹 <small></small></h1>",
                "<form method='get' id='form'>",
                "  <fieldset>",
                "    <div class='form-group row'>",
                "        <div class='col-10'>",
                "            <input type='text' class='form-control' name='ud' required />",
                "        </div>",
                "        <div class='col-2'>",
                "            <button class='btn btn-primary'>查轨迹</button>",
                "        </div>",
                "    </div>",
                "    <small id='tips' class='form-text'></small>",
                "  </fieldset>",
                "</form>",
                "<div class='row'>",
                "  <div class='col-3' id='left' style='border-right: 1px solid #ccc;min-height:400px;'>",
                "  </div>",
                "  <div class='col-9' id='right'>",
                "  </div>",
                "</div>"
            ];

            this.container.html(nodes.join(""));
            this.form = this.container.find("#form");
            this.fieldset = this.form.find("fieldset");
            this.leftPanel = this.container.find("#left");
            this.rightPanel = this.container.find("#right");

            self.loadData();
        };

        this.loadData = function(start, end) {

            $.getJSON(self.udSampleUrl, {}, function(resp){
                var uds = [];
                for (var i=0; i<resp.sample.length; i++) {
                    uds.push("<li><a href='javascript:void()'><small>" + resp.sample[i] + "</small></a></li>");
                }

                var html = [
                    "<strong>Total: " + resp.count + "</strong>",
                    "<ul class='list-unstyled'>",
                    uds.join(""),
                    "</ul>"
                ].join("");
                self.leftPanel.html(html);

                self.leftPanel.find("a").bind("click", function(e) {
                    var link = $(e.target);
                    self.form.find("input[name=ud]").val(link.html());
                    self.form.find("button").click();
                });
            });

        };

        this.renderWordTable = function(resp) {
            var headers = [
                "<tr>",
                "    <th>Word</th>",
                "    <th>Score</th>",
                "</tr>",
            ].join("");

            var body = [];
            for(var i=0; i<resp.word.items.length; i++) {
                var item = resp.word.items[i];
                var itemHtml = [
                    "<tr>",
                    "    <td>" + item[0] + "</td>",
                    "    <td>" + item[1] + "</td>",
                    "</tr>"
                ].join("");
                body.push(itemHtml);
            }

            var html = [
                "<strong>Total " + resp.word.count + " liked words</strong>",
                "<table class='table table-bordered table-sm'>",
                headers,
                body.join(""),
                "</table>"
            ].join("");

            return html;
        };

        this.renderShowTable = function(resp) {
            var headers = [
                "<tr>",
                "    <th>Paper</th>",
                "    <th>Count</th>",
                "</tr>",
            ].join("");

            var body = [];
            for(var i=0; i<resp.show.items.length; i++) {
                var item = resp.show.items[i];
                var itemHtml = [
                    "<tr>",
                    "    <td>" + item[0] + "</td>",
                    "    <td>" + item[1] + "</td>",
                    "</tr>"
                ].join("");
                body.push(itemHtml);
            }

            var html = [
                "<strong>Total " + resp.show.count + " show</strong>",
                "<table class='table table-bordered table-sm'>",
                headers,
                body.join(""),
                "</table>"
            ].join("");

            return html;
        };

        this.renderRecommendationTable = function(resp) {
            var headers = [
                "<tr>",
                "    <th>Paper</th>",
                "    <th>Score</th>",
                "</tr>",
            ].join("");

            var body = [];
            for(var i=0; i<resp.recommend.items.length; i++) {
                var item = resp.recommend.items[i];
                var itemHtml = [
                    "<tr>",
                    "    <td>" + item[0] + "</td>",
                    "    <td>" + item[1] + "</td>",
                    "</tr>"
                ].join("");
                body.push(itemHtml);
            }

            var html = [
                "<strong>Total " + resp.recommend.count + " recommend</strong>",
                "<table class='table table-bordered table-sm'>",
                headers,
                body.join(""),
                "</table>"
            ].join("");

            return html;
        };

        this.render();

        this.form.submit(function(e) {
           e.preventDefault();

           var ud = self.form.find("input[name=ud]").val();

           self.fieldset.attr("disabled", true);
           self.form.find("#tips").html(self.spin);
           $.ajax({
               url: self.udActionUrl,
               method: "get",
               dataType: "json",
               data: {ud: ud},
               success: function(resp) {
                    console.debug(resp);
                    self.fieldset.removeAttr("disabled");
                    self.form.find("#tips").html("");

                    var html = self.renderWordTable(resp);
                    html += self.renderShowTable(resp);
                    html += self.renderRecommendationTable(resp);

                    self.rightPanel.html(html);
               },
               error: function(xhr, status, err) {
                   console.debug(err);
                   self.form.find("#tips").html(err);
                   self.fieldset.removeAttr("disabled");
               }
           });

        });

    };

    exports.UdStatus = UdStatus;
})(window);