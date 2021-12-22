/* globals Chart:false, feather:false */

(function () {
  'use strict'

  feather.replace({ 'aria-hidden': 'true' })

  // Graphs
  var ctx1 = document.getElementById('myChart1')
  // eslint-disable-next-line no-unused-vars
  var myChart1 = new Chart(ctx1, {
    type: 'line',
    data: {
      labels: [
        '0',
        '0',
        '0',
        '0',
        '0',
        '0',
        '0'
      ],
      datasets: [{
        data: [
          0,
          0,
          0,
          0,
          0,
          0,
          0
        ],
        lineTension: 0,
        backgroundColor: 'transparent',
        borderColor: '#007bff',
        borderWidth: 4,
        pointBackgroundColor: '#007bff'
      }]
    },
    options: {
      scales: {
        yAxes: [{
          ticks: {
            beginAtZero: false
          }
        }]
      },
      legend: {
        display: false
      }
    }
  })

  


var ctx2 = document.getElementById('myChart2')
  // eslint-disable-next-line no-unused-vars
  var myChart2 = new Chart(ctx2, {
    type: 'line',
    data: {
      labels: [
        '0',
        '0',
        '0',
        '0',
        '0',
        '0',
        '0'
      ],
      datasets: [{
        data: [
          0,
          0,
          0,
          0,
          0,
          0,
          0
        ],
        lineTension: 0,
        backgroundColor: 'transparent',
        borderColor: '#007bff',
        borderWidth: 4,
        pointBackgroundColor: '#007bff'
      }]
    },
    options: {
      scales: {
        yAxes: [{
          ticks: {
            beginAtZero: false
          }
        }]
      },
      legend: {
        display: false
      }
    }
  })

})()

