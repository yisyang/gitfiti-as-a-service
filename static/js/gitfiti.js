"use strict";
window.onload = function () {
  // Generate empty chart for 366 days.
  let chartData = [];
  let time = Date.now();
  for (let i = 0; i < 366; i++) {
    chartData.unshift({
      date: new Date(time - i * 86400000),
      count: 0
    });
  }

  // Customize color brackets.
  let colorBrackets = [
    {
      'color': '#eeeeee',
      'min': 0
    },
    {
      'color': '#c6e48b',
      'min': 1
    },
    {
      'color': '#7bc96f',
      'min': 5
    },
    {
      'color': '#239a3b',
      'min': 10
    },
    {
      'color': '#196127',
      'min': 14
    }
  ];
  let maxCount = 24;

  // 'auto' to darken color to next bracket, or reset to 0 when at max.
  // Any integer <= maxCount to set day contributions to said integer.
  let brushSize = 'auto';

  // Initialize array of commits to push.
  let commitsToPush = [];

  // Track mouse state.
  let mouseDown = 0;
  document.body.addEventListener('mousedown', () => mouseDown = 1);
  document.body.addEventListener('mouseup', () => mouseDown = 0);

  // Set up brushes.
  document.querySelectorAll('.brush-holder').forEach(bh => {
    bh.addEventListener('click', () => {
      if (bh.getAttribute('data-brush-index').length) {
        setBrushSize(colorBrackets[Number(bh.getAttribute('data-brush-index'))].min);
      } else {
        setBrushSize('auto');
      }
      document.querySelectorAll('.brush-holder').forEach(bhOther => {
        bhOther.removeAttribute('data-selected');
      });
      bh.setAttribute('data-selected', '1');
    })
  });

  // Set up chart.
  let contributionsChart = calendarHeatmap()
    .data(chartData)
    .selector('#contributions-graph')
    .max(maxCount)
    .colorBrackets(colorBrackets)
    .tooltipEnabled(true)
    .tooltipUnit(
      [
        { min: colorBrackets[0].min, unit: 'contribution' },
        { min: colorBrackets[1].min, unit: 'contribution' },
        { min: colorBrackets[2].min, unit: 'contributions' },
        { min: colorBrackets[3].min, unit: 'contributions' },
        { min: colorBrackets[4].min, max: 'Infinity', unit: 'contributions' }
      ]
    )
    .onMouseDown(function (data, elem) {
      updateElementAndData(elem, data);
    })
    .onMouseEnter(function (data, elem) {
      if (!mouseDown) {
        return;
      }
      updateElementAndData(elem, data);
    });

  // Render chart.
  contributionsChart();

  // Block default mouse behavior.
  document.querySelector('#contributions-graph').addEventListener('click', (e) => e.preventDefault());
  document.querySelector('#contributions-graph').addEventListener('mousedown', (e) => e.preventDefault());

  // Block tooltip while drawing.
  document.body.addEventListener('mousedown', () => contributionsChart.tooltipEnabled(false));
  document.body.addEventListener('mouseup', () => contributionsChart.tooltipEnabled(true));

  // Submit buttons.
  document.querySelector('#verify-button').addEventListener('click', () => computeChanges());
  document.querySelector('#push-button').addEventListener('click', () => submitCommits());

  /**
   * Compute changes from canvas.
   */
  function computeChanges() {
    let data = contributionsChart.data();
    let commits = [];
    let commitsTotal = 0;
    let maxRangePresent = false;
    for (let datum of data) {
      if (datum.count > 0) {
        let count = datum.count;

        // Before submitting requests, check that at least 1 usage of largest
        // bracket (14) is present.
        // When submitting requests, convert 1st largest bracket usage (14)
        // into max (24), this is required for proper color scaling.
        if (!maxRangePresent && count === 14) {
          maxRangePresent = true;
          count = 24;
        }
        commits.push({
          "date": moment.utc(datum.date).format().replace('+00:00', 'Z'),
          "count": count
        });
        commitsTotal += count;
      }
    }

    if (maxRangePresent) {
      commitsToPush = commits;
      document.querySelector('#verify-result-message').className = 'message-success';
      document.querySelector('#verify-result-message').innerText = commitsTotal + ' commits ready to be pushed.';
      document.querySelector('#push-button').removeAttribute('disabled');
      document.querySelector('#push-result-message').className = 'message-hidden';
    } else {
      commitsToPush = [];
      document.querySelector('#verify-result-message').className = 'message-error';
      document.querySelector('#verify-result-message').innerText = 'Invalid data. Please ensure at least 1 commit contains the darkest color.';
      document.querySelector('#push-button').setAttribute('disabled', 'disabled');
      document.querySelector('#push-result-message').className = 'message-hidden';
    }
  }

  /**
   * Set brush size for making art.
   *
   * @param {string|int} newBrushSize
   */
  function setBrushSize(newBrushSize) {
    brushSize = newBrushSize;
  }

  /**
   * Set new count for cell described by data in canvas.
   *
   * @param data
   * @param {int} newCount
   */
  function setNewCount(data, newCount) {
    let dataFound = contributionsChart.data().find(function (element) {
      return moment(element.date).isSame(data.date, 'day');
    });
    if (dataFound) {
      dataFound.count = newCount;
    } else {
      contributionsChart.data().push({
        'date': data.date,
        'count': newCount
      });
    }
  }

  /**
   * Submit changes to API, for API to push.
   */
  function submitCommits() {
    // First disable button.
    document.querySelector('#verify-result-message').className = 'message-hidden';
    document.querySelector('#push-button').setAttribute('disabled', 'disabled');

    // Display loading message.
    document.querySelector('#push-result-message').className = 'message-pending';
    document.querySelector('#push-result-message').innerText = 'Processing...';

    // Send request.
    let req = new XMLHttpRequest();
    req.addEventListener("load", submitCommitCallback);
    req.open("POST", "/post-commits-to-github");
    req.setRequestHeader("Content-Type", "application/json");
    req.send(JSON.stringify({ commits: commitsToPush }));
  }

  /**
   * Callback for submit to API.
   */
  function submitCommitCallback() {
    let resp = JSON.parse(this.responseText);
    if (this.status === 200) {
      document.querySelector('#push-result-message').className = 'message-success';
      document.querySelector('#push-result-message').innerText = resp.message;
    } else {
      document.querySelector('#push-result-message').className = 'message-error';
      document.querySelector('#push-result-message').innerText = resp && resp.message ? resp.message : 'Server error.';
    }
  }

  /**
   * Update canvas.
   *
   * @param elem DOM SVG Element.
   * @param data {object} Object with keys of date and count.
   */
  function updateElementAndData(elem, data) {
    let newCount;

    // Compute new count.
    if (brushSize === 'auto') {
      for (let i = colorBrackets.length - 1; i >= 0; i--) {
        if (data.count >= colorBrackets[i].min) {
          if (i === colorBrackets.length - 1) {
            newCount = colorBrackets[0].min;
            break;
          }
          newCount = colorBrackets[i + 1].min;
          break;
        }
      }
    } else {
      newCount = brushSize;
    }

    // Update data and fill square.
    for (let i = colorBrackets.length - 1; i >= 0; i--) {
      if (newCount >= colorBrackets[i].min) {
        // Set new count.
        setNewCount(data, newCount);
        // Set new fill color.
        elem.setAttribute('fill', colorBrackets[i].color);
        break;
      }
    }
  }
};
