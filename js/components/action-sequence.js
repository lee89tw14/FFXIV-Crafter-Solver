'use strict';

angular.module('ffxivCraftOptWeb.components')
  .directive('actionSequence', function () {
    return {
      restrict: 'E',
      templateUrl: 'components/action-sequence.html',
      scope: {
        actions: '=',
        cls: '=',
        onClick: '=',
        actionClasses: '=',
        draggable: '=',
        tooltipPlacement: '@'
      },
      controller: function ($scope, $rootScope, $translate, _allActions, _allClasses, _actionGroups, _actionsByName, _xivdbtooltips, _getActionImagePath) {
        $scope.actionGroups = _actionGroups;

        $scope.getActionImagePath = _getActionImagePath;

        $scope.actionTooltip = _xivdbtooltips.actionTooltip.bind(_xivdbtooltips);

        $scope._actionClasses = function (action, cls) {
          var classes = {};
          if ($scope.actionClasses) {
            classes = $scope.actionClasses(action, cls);
          }
          return classes;
        }
      }
    }
  });