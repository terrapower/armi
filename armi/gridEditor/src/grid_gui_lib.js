/**
* Copyright 2022 Google, LLC
*
* Licensed under the Apache License, Version 2.0 (the "License");
* you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
*
*     http://www.apache.org/licenses/LICENSE-2.0
*
* Unless required by applicable law or agreed to in writing, software
* distributed under the License is distributed on an "AS IS" BASIS,
* WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
* See the License for the specific language governing permissions and
* limitations under the License.
*/
/**
* Part of a working prototype for a notebook-based replacement for the
*  wxPython-based grid editor GUI.
*/
import * as d3 from "d3";

const SQRT3 = Math.sqrt(3);

const UNIT_HEXAGON = [
    [+1, 0],
    [+0.5, -SQRT3 * 0.5],
    [-0.5, -SQRT3 * 0.5],
    [-1, 0],
    [-0.5, +SQRT3 * 0.5],
    [+0.5, +SQRT3 * 0.5],
];

const DEFAULT_CELL_WIDTH = 40;   // For Cartesian grid
const DEFAULT_CELL_RADIUS = 30;  // For Hexagonal grid

// Global variable that holds the text contents of the debug console.
// Hacky, but works.
let consoleLogContents = "Debug console.";

const celltypeSelectorData = {
    "isEmpty": true,
    "specifier": null,
    "rgb": null,
};

const fuelPathContext = {
    "isFuelPathMode": false,
};

// Global variable that maps the specifiers to the names and colors.
// This is loaded from "data" in the main function.
let specifierMap = {};

const DI_DJ_LIST = [
    [+1, -1],
    [+0, -1],
    [-1, +0],
    [-1, +1],
    [+0, +1],
    [+1, +0],
];

function numRingsToIjList(numRings) {
/** Generates a list of (i,j) coordinates for a full hexagonal core.

    Args:
        numRings: Number of rings. Must be an integer 1 or greater.

    Returns:
        List of (i, j) coordinates.
    */
    const ijList = [];
    for (let r = 0; r < numRings; r++) {
        if (r == 0) {
            ijList.push([0, 0]);
        } else {
            let i = 0;
            let j = r;
            for (let di_dj of DI_DJ_LIST) {
                for (let rr = 0; rr < r; rr++) {
                    const di = di_dj[0];
                    const dj = di_dj[1];
                    ijList.push([i, j]);
                    i += di;
                    j += dj;
                }
            }
        }
    }
    return ijList;
}

function ijToXHexCenter(i, j, radius, xOffset) {
/** Converts an (i, j) coordinate to the x-OffSet of the center of the hexagon.

    Args:
        i: i-coordinate in a hexagonal grid.
        j: j-coordinate in a hexagonal grid.
        radius: Distance between the center of the hexagon to its corner.
        xOffset: Any additional xOffset to add to the result.

    Returns:
        The xOffset.
    */
    return (SQRT3 * i) * radius * (SQRT3 / 2) + xOffset;
}

function ijToYHexCenter(i, j, radius, yOffset) {
/** Converts an (i, j) coordinate to the y-OffSet of the center of the hexagon.

    Args:
        i: i-coordinate in a hexagonal grid.
        j: j-coordinate in a hexagonal grid.
        radius: Distance between the center of the hexagon to its corner.
        yOffset: Any additional yOffset to add to the result.

    Returns:
        The yOffset.
    */
    return -(i + j * 2) * radius * (SQRT3 / 2) + yOffset;
}

function ijToHexCorners(i, j, radius, xOffset, yOffset) {
/** Converts an (i, j) coord to a list of 6 corners of the hexagon in XY coords.

    Args:
        i: i-coordinate in a hexagonal grid.
        j: j-coordinate in a hexagonal grid.
        radius: Distance between the center of the hexagon to its corner.
        xOffset: Any additional xOffset to add to the results.
        yOffset: Any additional yOffset to add to the results.

    Returns:
        List containing 6 (x,y) coordinates, one for each corner of the hexagon.
    */
    const hexCornersList = [];
    const xHexCenter = ijToXHexCenter(i, j, radius, xOffset);
    const yHexCenter = ijToYHexCenter(i, j, radius, yOffset);
    for (let [x, y] of UNIT_HEXAGON) {
        x = x * radius + xHexCenter;
        y = y * radius + yHexCenter;
        hexCornersList.push([x, y]);
    }
    return hexCornersList;
}

function backGroundRGBToString(backgroundRGB) {
/** Converts a RGB array to an RGB string. */
    const [r, g, b] = backgroundRGB;
    return "rgb(" + r + "," + g + "," + b + ")";
}

function textColorForBackground(backgroundRGB) {
/** Computes text color that is readable against from the background color. */
    const [r, g, b] = backgroundRGB;
    const relativeLuminance = (0.2126 * r + 0.7132 * g + 0.0722 * b) / 255;
    let textColor = "black";
    if (relativeLuminance < 0.51) {
        textColor = "white";
    }
    return textColor;
}

function rgbToHsl(rgb) {
/** Converts RGB values to HSL.

    Note that the returned s and l are between 0 and 1 (not between 0 and 100).
    */
    const [r_rel, g_rel, b_rel] = [rgb[0] / 255, rgb[1] / 255, rgb[2] / 255];
    const [c_max, c_min] = [Math.max(...rgb) / 255, Math.min(...rgb) / 255];
    const delta = c_max - c_min;
    const l = (c_max + c_min) / 2;
    const s = delta ? (delta / (1 - Math.abs(2 * l - 1))) : 0;
    let h = 0;
    if (delta === 0) {
        h = 0;
    } else if (c_max === r_rel) {
        h = 60 * ((6 + ((g_rel - b_rel) / delta)) % 6);
    } else if (c_max === g_rel) {
        h = 60 * (((b_rel - r_rel) / delta) + 2);
    } else if (c_max === b_rel) {
        h = 60 * (((r_rel - g_rel) / delta) + 4);
    }

    return [h, s, l];
}

function hslToRgb(hsl) {
/** Converts HSL values to RGB.

    Note that the expected s and l are between 0 and 1 (not between 0 and 100).
    */
    const [h, s, l] = hsl;
    const c = (1 - Math.abs(2 * l - 1)) * s;
    const x = c * (1 - Math.abs((h / 60) % 2 - 1));
    const m = l - c / 2;
    let [r_rel, g_rel, b_rel] = [0, 0, 0];
    if (0 <= h && h < 60) {
        [r_rel, g_rel, b_rel] = [c, x, 0];
    } else if (60 <= h && h < 120) {
        [r_rel, g_rel, b_rel] = [x, c, 0];
    } else if (120 <= h && h < 180) {
        [r_rel, g_rel, b_rel] = [0, c, x];
    } else if (180 <= h && h < 240) {
        [r_rel, g_rel, b_rel] = [0, x, c];
    } else if (240 <= h && h < 300) {
        [r_rel, g_rel, b_rel] = [x, 0, c];
    } else {
        [r_rel, g_rel, b_rel] = [c, 0, x];
    }
    return [(r_rel + m) * 255, (g_rel + m) * 255, (b_rel + m) * 255];
}

function desaturateFn(backgroundRGB) {
/** Computes a desaturated RGB value. */
    const [h, s, l] = rgbToHsl(backgroundRGB);
    const l_new = l + (1.0 - l) * 0.5;
    return hslToRgb([h, s, l_new]);
}

function gridCellClickHandler() {
/** Handles grid cell being clicked. */
    const i = d3.select(this).attr("gridcell-i");
    const j = d3.select(this).attr("gridcell-j");
    const polygonElement = d3.select(
        `#grid-area polygon[gridcell-i="${i}"][gridcell-j="${j}"]`);
    const textElement = d3.select(
        `#grid-area text[gridcell-i="${i}"][gridcell-j="${j}"]`);
    if (!fuelPathContext["isFuelPathMode"]) {
        if (celltypeSelectorData["isEmpty"]) {
            consoleLog(`cell (${i},${j}) clicked. unsetting celltype.`);
            polygonElement
                .style("fill", "rgb(200,200,200)");
            textElement
                .attr("fill", "black")
                .text(`${i},${j}`);
        } else {
            const specifier = celltypeSelectorData["specifier"];
            const rgb = celltypeSelectorData["rgb"];
            consoleLog(
                `cell (${i},${j}) clicked. setting celltype to ${specifier}.`);
            polygonElement
                .attr("gridcell-specifier", specifier)
                .attr("gridcell-r", rgb[0])
                .attr("gridcell-g", rgb[1])
                .attr("gridcell-b", rgb[2])
                .style("fill", backGroundRGBToString(rgb));
            textElement
                .attr("gridcell-specifier", specifier)
                .attr("fill", textColorForBackground(rgb))
                .text(specifier);
        }
    } else {
        const path = d3.select("#fuel_path_input").property("value");
        const index = d3.select("#fuel_path_index").property("value");
        consoleLog(
            `cell (${i},${j}) clicked. `
            `resaturate and label w fuel path (${path},${index}).`);
        const r = polygonElement.attr("gridcell-r");
        const g = polygonElement.attr("gridcell-g");
        const b = polygonElement.attr("gridcell-b");
        polygonElement.attr("gridcell-desaturate", "false");
        polygonElement.style("fill", backGroundRGBToString([r, g, b]));
        textElement.attr("fill", textColorForBackground([r, g, b]))
            .text(`${path},${index}`);
    }
}

function updateDrawChart(svg, scale, xOffset, yOffset, data) {
    const geomtype = data["geomtype"];
    const points = data["points"];
    const g = svg.selectAll("g").data(points).enter().append("g");

    if (geomtype == "cartesian") {
        const l = DEFAULT_CELL_WIDTH * scale;

        g.attr("width", l).attr("height", l);

        g.append("rect")
            .attr("x", (d) => d.x * l + xOffset)
            .attr("y", (d) => d.y * l + yOffset)
            .attr("width", l).attr("height", l)
            .attr("stroke", "black")
            .attr("stroke-width", "2px")
            .style("fill", "white");

        g.append("text")
            .text((d) => d.text)
            .attr("x", (d) => d.x * l + xOffset)
            .attr("y", (d) => d.y * l + yOffset)
            .attr("transform", `translate(${l/2},${l/2})`)
            .attr("dominant-baseline", "middle")
            .attr("text-anchor", "middle")
            .attr("class", "grid-gui-gridcell");
    } else if (geomtype == "hex") {
        const radius = DEFAULT_CELL_RADIUS * scale;
        g.append("polygon")
            .attr("gridcell-i", (d) => d.i)
            .attr("gridcell-j", (d) => d.j)
            .attr("gridcell-specifier", (d) => d.specifier)
            .attr("gridcell-r", (d) => specifierMap[d.specifier]["color"][0])
            .attr("gridcell-g", (d) => specifierMap[d.specifier]["color"][1])
            .attr("gridcell-b", (d) => specifierMap[d.specifier]["color"][2])
            .attr("gridcell-desaturate", "false")
            .attr("points",
                  (d) => ijToHexCorners(d.i, d.j, radius,
                                        350 + xOffset, 350 + yOffset))
            .attr("stroke", "black")
            .attr("stroke-width", "1px")
            .style("fill",
                   (d) => backGroundRGBToString(
                       specifierMap[d.specifier]["color"]))
            .on("click", gridCellClickHandler);

        g.append("text")
            .text((d) => d.specifier)
            .attr("gridcell-i", (d) => d.i)
            .attr("gridcell-j", (d) => d.j)
            .attr("gridcell-specifier", (d) => d.specifier)
            .attr("x", (d) => ijToXHexCenter(d.i, d.j, radius, 350 + xOffset))
            .attr("y", (d) => ijToYHexCenter(d.i, d.j, radius, 350 + yOffset))
            .attr("dominant-baseline", "middle")
            .attr("text-anchor", "middle")
            .attr("class", "grid-gui-gridcell")
            .attr("fill", (d) => textColorForBackground(
                specifierMap[d.specifier]["color"]))
            .on("click", gridCellClickHandler);
    }
}

function defineNavBar(navBar) {
    navBar.attr("id", "navbar");
    navBar.append("a")
        .attr("class", "navbar-brand")
        .attr("href", "#")
        .text("Grid Editor");
}

function defineDisplayArea(displayArea, data) {
    const widthGuiBox = 700;
    const heightGuiBox = 700;

    let zoom = d3.zoom().on("zoom", (e) => {
        let g = d3.selectAll("#grid-area g");
        consoleLog("inside handleZoom. e.transform: " + e.transform);
        g.attr("transform", e.transform);
    });

    const svg = displayArea.append("svg")
        .attr("id", "grid-area")
        .attr("width", widthGuiBox)
        .attr("height", heightGuiBox)
        .call(zoom);

    svg.append("rect")
        .attr("x", 0)
        .attr("y", 0)
        .attr("width", widthGuiBox)
        .attr("height", heightGuiBox)
        .style("fill", "none");

    updateDrawChart(svg, 1.0, 0, 0, data);
}

function defineSidePanel(sidePanel) {
    sidePanel.attr("id", "side-panel");

    sidePanel.append("h4").text("Assemblies").style("padding-bottom", "0.75em");

    const legendData = [];
    for (const [specifier, item] of Object.entries(specifierMap)) {
        if (specifier === "-") {
            continue;
        }
        const l = {
            "specifier": specifier,
            "name": item["name"],
            "color": item["color"],
        };
        legendData.push(l);
    }
    const legend = sidePanel.append("div");

    let g = legend.selectAll("g").data(legendData).enter().append("g");
    const legend_radius = DEFAULT_CELL_RADIUS;
    g = g.style("display", "flex")
        .style("flex-direction", "row")
        .style("align-items", "stretch")
        .style("width", "100%")
        .style("height", `${2 * legend_radius}px`);
    const svg = g.append("svg")
        .style("display", "inline-block")
        .style("width", `${2 * legend_radius}px`)
        .style("height", `${2 * legend_radius}px`);
    svg.append("polygon")
        .attr("points", ijToHexCorners(0, 0, legend_radius, legend_radius, legend_radius))
        .attr("stroke", "black")
        .attr("stroke-width", "1px")
        .style("fill", (d) => backGroundRGBToString(d.color));
    svg.append("text")
        .text((d) => d.specifier)
        .attr("x", (d) => ijToXHexCenter(0, 0, legend_radius, legend_radius))
        .attr("y", (d) => ijToYHexCenter(0, 0, legend_radius, legend_radius))
        .attr("dominant-baseline", "middle")
        .attr("text-anchor", "middle")
        .attr("class", "grid-gui-gridcell")
        .attr("fill", (d) => textColorForBackground(d.color));

    g.append("button")
        .style("display", "inline-flex")
        .style("align-items", "center")
        .style("text-align", "center")
        .style("padding", "auto")
        .style("width", `${240 - 2 * legend_radius}px`)
        .attr("type", "button")
        .attr("class", "my-button")
        .attr("class", "selector-button")
        .attr("aria-pressed", "false")
        .attr("celltype-selector-specifier", (d) => d.specifier)
        .attr("celltype-selector-red", (d) => d.color[0])
        .attr("celltype-selector-green", (d) => d.color[1])
        .attr("celltype-selector-blue", (d) => d.color[2])
        .text((d) => d.name)
        .on("click", function(e) {
            const specifier = d3.select(this)
                .attr("celltype-selector-specifier");
            const r = d3.select(this).attr("celltype-selector-red");
            const g = d3.select(this).attr("celltype-selector-green");
            const b = d3.select(this).attr("celltype-selector-blue");
            // Remember this button state.
            let pressed = e.target.getAttribute("aria-pressed") === "true";
            // Deselect all other buttons
            d3.selectAll(".selector-button").attr("aria-pressed", "false");
            if (!pressed) {
                d3.select(this).attr("aria-pressed", "true");
                pressed = e.target.getAttribute("aria-pressed");
                celltypeSelectorData["isEmpty"] = false;
                celltypeSelectorData["specifier"] = specifier;
                celltypeSelectorData["rgb"] = [r, g, b];
            } else {
                celltypeSelectorData["isEmpty"] = true;
                celltypeSelectorData["specifier"] = null;
                celltypeSelectorData["rgb"] = null;
            }
            consoleLog(`celltype-selector clicked. `
                       `specifier: ${celltypeSelectorData["specifier"]}`);
        });

    sidePanel.append("h4")
        .text("Equilibrium Fuel Path")
        .style("padding-bottom", "0.75em");
    const fuelPathButtonRow = sidePanel.append("div")
        .style("display", "flex")
        .style("flex-direction", "row");
    fuelPathButtonRow.append("button")
        .attr("type", "button")
        .attr("class", "my-button")
        .attr("id", "fuel_path_btn")
        .attr("font-size", "10px")
        .attr("aria-pressed", "false")
        .style("display", "inline")
        .style("padding-left", "4.2px")
        .style("padding-right", "4.2px")
        .text("Fuel Path")
        .on("click", function(e) {
            consoleLog("fuel_path_btn clicked. Changing cell saturation.");
            // Remember this button state.
            let pressed = e.target.getAttribute("aria-pressed") === "true";
            if (!pressed) {
                d3.select(this).attr("aria-pressed", "true");
                fuelPathContext["isFuelPathMode"] = true;
            } else {
                d3.select(this).attr("aria-pressed", "false");
                fuelPathContext["isFuelPathMode"] = false;
            }
            if (fuelPathContext["isFuelPathMode"]) {
                d3.selectAll("#grid-area polygon").style("fill", function() {
                    let r = d3.select(this).attr("gridcell-r");
                    let g = d3.select(this).attr("gridcell-g");
                    let b = d3.select(this).attr("gridcell-b");
                    const desaturate = (
                        d3.select(this).attr("gridcell-desaturate") === "true");
                    const newDesaturate = !desaturate;
                    d3.select(this).attr("gridcell-desaturate",
                                         newDesaturate ? "true" : "false");
                    if (newDesaturate) {
                     [r, g, b] = desaturateFn([r, g, b]);
                    }
                    return backGroundRGBToString([r, g, b]);
                });
                d3.selectAll("#grid-area text").text(function() {
                    const polygon = d3.select(this.parentNode).select("polygon");
                    const desaturate = (
                        polygon.attr("gridcell-desaturate") === "true");
                    if (desaturate) {
                      return "-";
                    }
                    return d3.select(this).attr("gridcell-specifier");
                });
                fuelPathContext["path"] = d3.select("#fuel_path_input")
                    .attr("value");
                fuelPathContext["index"] = d3.select("#fuel_path_index")
                    .attr("value");
            } else {
                d3.selectAll("#grid-area polygon").style("fill", function() {
                    let r = d3.select(this).attr("gridcell-r");
                    let g = d3.select(this).attr("gridcell-g");
                    let b = d3.select(this).attr("gridcell-b");
                    return backGroundRGBToString([r, g, b]);
                }).attr("gridcell-desaturate", "false");
                d3.selectAll("#grid-area text").text(function() {
                    return d3.select(this).attr("gridcell-specifier");
                });
            }
        });

    fuelPathButtonRow.append("button")
        .attr("type", "button")
        .attr("class", "my-button")
        .attr("id", "rm_fuel_path_btn")
        .attr("font-size", "10px")
        .style("display", "inline")
        .style("padding-left", "4.2px")
        .style("padding-right", "4.2px")
        .text("Remove From Fuel Path");

    const fuelPathInputRow = sidePanel.append("div")
        .style("display", "flex")
        .style("flex-direction", "row");
    fuelPathInputRow.append("text")
        .text("Path: ");
    fuelPathInputRow.append("input")
        .attr("type", "number")
        .attr("id", "fuel_path_input")
        .attr("min", 0)
        .attr("value", 0);

    const fuelPathIndexRow = sidePanel.append("div")
        .style("display", "flex")
        .style("flex-direction", "row");
    fuelPathIndexRow.append("text")
        .text("Index: ");
    fuelPathIndexRow.append("input")
        .attr("type", "number")
        .attr("id", "fuel_path_index")
        .attr("min", 0)
        .attr("value", 0);
}

function defineMiddleContainer(middleContainer, data) {
    middleContainer.attr("id", "middle-container");
    const displayArea = middleContainer.append("div");
    defineDisplayArea(displayArea, data);
    const sidePanel = middleContainer.append("div");
    defineSidePanel(sidePanel);
}

function defineBottomPanel(bottomPanel) {
    const bottomBoxArea = bottomPanel
        .attr("id", "bottom-box-area");

    bottomBoxArea.append("div")
        .style("width", "100%")
        .text("Num. Rings");
    bottomBoxArea.append("div");
    bottomBoxArea.append("div");
    bottomBoxArea.append("div");
    bottomBoxArea.append("div");
    bottomBoxArea.append("div").append("input")
        .attr("type", "number")
        .attr("id", "numRings")
        .style("width", "100%")
        .style("height", "90%")
        .attr("min", 1)
        .attr("max", 20)
        .attr("value", 5)
        .attr("title", "Select how many rings of the grid to display");

    bottomBoxArea.append("div");
    bottomBoxArea.append("div");
    bottomBoxArea.append("div");
    bottomBoxArea.append("div");

    bottomBoxArea.append("button")
        .attr("type", "button")
        .attr("class", "my-button")
        .attr("id", "apply_button")
        .text("Apply")
        .on("click", () => {
            // Update the number of rings.
            const numRings = d3.select("#numRings").property("value");
            const dataDict = {"geomtype": "hex"};
            const points = [];
            const ijList = numRingsToIjList(numRings);
            for (let [i, j] of ijList) {
                points.push(
                    {"i": i, "j": j, "specifier": "-"}
                );
            }
            dataDict["points"] = points;
            const displayAreaSvg = d3.select("#grid-area");
            displayAreaSvg.selectAll("g").remove();
            updateDrawChart(displayAreaSvg, 1.0, 0, 0, dataDict);
        });


    bottomBoxArea.append("div");
    bottomBoxArea.append("button")
        .attr("type", "button")
        .attr("class", "my-button")
        .attr("id", "export_ascii_button")
        .text("Export points")
        .on("click", () => {
            // Export ASCII Map.
            const comm = new CommAPI("test",
                () => { consoleLog("points export complete."); });
            const points = [];
            d3.selectAll("#grid-area polygon").each(function() {
                const point = {};
                point["i"] = parseInt(d3.select(this).attr("gridcell-i"));
                point["j"] = parseInt(d3.select(this).attr("gridcell-j"));
                point["specifier"] = d3.select(this).attr("gridcell-specifier");
                points.push(point);
            })
            comm.call({"points": points});
        });
}

function consoleLog(logStr) {
/** Logs to the debug console at the bottom of the UI. */
    consoleLogContents += "\n" + logStr;
    const debugConsole = d3.select("#debug-console");
    if (debugConsole) {
        debugConsole.property("value", consoleLogContents);
        // Force the debug console to scroll to the bottom.
        const scrollHeight = debugConsole.property("scrollHeight");
        debugConsole.property("scrollTop", scrollHeight);
    }
}

function defineDebugPanel(debugPanel) {
    const debugConsole = debugPanel.append("textarea")
        .attr("id", "debug-console")
        .style("width", "100%")
        .property("value", consoleLogContents);
}

export function main(id, data) {
    specifierMap = data["specifierMap"];

    const root = d3.select(id);
    root.attr("class", "gray-background");

    const navBar = root.append("nav");
    defineNavBar(navBar);

    const middleContainer = root.append("div");
    defineMiddleContainer(middleContainer, data);

    const bottomPanel = root.append("div");
    defineBottomPanel(bottomPanel);

    const debugPanel = root.append("div");
    defineDebugPanel(debugPanel);
}
