import numpy as np
import pytest

from wildcat._commands.assess import _model


class TestM1Variables:
    def test_already_computed(_, logcheck):
        properties = {"Terrain_M1": 1, "Fire_M1": 2, "Soil_M1": 3}
        _model._m1_variables(None, None, properties, logcheck.log)
        assert properties == {"Terrain_M1": 1, "Fire_M1": 2, "Soil_M1": 3}
        logcheck.check([])

    def test(_, segments, rasters, slope23, logcheck):

        rasters["slopes"] = slope23
        properties = {}
        _model._m1_variables(segments, rasters, properties, logcheck.log)
        assert list(properties.keys()) == ["Terrain_M1", "Fire_M1", "Soil_M1"]
        expected = {
            "Terrain_M1": [
                0.25,
                0.36363636,
                0.3902439,
                0.2962963,
                0.32,
                0.2,
                0.0,
                0.0625,
            ],
            "Fire_M1": [
                0.2125,
                0.39972727,
                0.33404878,
                0.31096296,
                0.30389333,
                0.24,
                0.23333333,
                0.23125,
            ],
            "Soil_M1": [
                0.2,
                0.2,
                0.51034483,
                0.53333333,
                0.48571429,
                0.4,
                0.31111111,
                0.325,
            ],
        }
        for key, values in expected.items():
            assert np.allclose(properties[key], values)
        logcheck.check([("DEBUG", "    Computing M1 variables")])


class TestLikelihood:
    def test(_, config, segments, rasters, m1_vars, logcheck):
        _model._likelihood(
            config["I15_mm_hr"], segments, rasters, m1_vars, logcheck.log
        )
        assert "likelihood" in m1_vars
        assert m1_vars["likelihood"].shape == (8, 3, 1)
        expected = np.array(
            [
                [
                    [0.11002361, 0.15373203, 0.21069354],
                    [0.19744073, 0.30038628, 0.42835867],
                    [0.33944157, 0.5188087, 0.69345555],
                    [0.30632435, 0.47148099, 0.64312649],
                    [0.28276936, 0.43635774, 0.60320832],
                    [0.17670979, 0.26580728, 0.37914002],
                    [0.10587792, 0.14685993, 0.20015381],
                    [0.11943936, 0.16942787, 0.23476014],
                ]
            ]
        ).reshape(8, 3, 1)
        assert np.allclose(m1_vars["likelihood"], expected)
        logcheck.check(
            [
                ("INFO", "Estimating debris-flow likelihood"),
                ("DEBUG", "    Running model"),
            ]
        )

    def test_get_variables(_, config, segments, rasters, slope23, logcheck):
        properties = {}
        rasters["slopes"] = slope23
        _model._likelihood(
            config["I15_mm_hr"], segments, rasters, properties, logcheck.log
        )
        assert "Terrain_M1" in properties
        assert "likelihood" in properties
        assert properties["likelihood"].shape == (8, 3, 1)
        expected = np.array(
            [
                [
                    [0.11002361, 0.15373203, 0.21069354],
                    [0.19744073, 0.30038628, 0.42835867],
                    [0.33944157, 0.5188087, 0.69345555],
                    [0.30632435, 0.47148099, 0.64312649],
                    [0.28276936, 0.43635774, 0.60320832],
                    [0.17670979, 0.26580728, 0.37914002],
                    [0.10587792, 0.14685993, 0.20015381],
                    [0.11943936, 0.16942787, 0.23476014],
                ]
            ]
        ).reshape(8, 3, 1)
        assert np.allclose(properties["likelihood"], expected)
        logcheck.check(
            [
                ("INFO", "Estimating debris-flow likelihood"),
                ("DEBUG", "    Computing M1 variables"),
                ("DEBUG", "    Running model"),
            ]
        )

    def test_keepdims(_, config, segments, rasters, m1_vars, logcheck):
        _model._likelihood(
            config["I15_mm_hr"][0:1], segments, rasters, m1_vars, logcheck.log
        )
        assert "likelihood" in m1_vars
        assert m1_vars["likelihood"].shape == (8, 1, 1)
        expected = np.array(
            [
                [
                    [0.11002361],
                    [0.19744073],
                    [0.33944157],
                    [0.30632435],
                    [0.28276936],
                    [0.17670979],
                    [0.10587792],
                    [0.11943936],
                ]
            ]
        ).reshape(8, 1, 1)
        assert np.allclose(m1_vars["likelihood"], expected)
        logcheck.check(
            [
                ("INFO", "Estimating debris-flow likelihood"),
                ("DEBUG", "    Running model"),
            ]
        )


class TestVolume:
    def test(_, config, segments, rasters, logcheck):
        properties = {}
        _model._volume(config, segments, rasters, properties, logcheck.log)
        assert list(properties.keys()) == ["Bmh_km2", "Relief_m", "V", "Vmin", "Vmax"]
        assert properties["V"].shape == (8, 3, 1)
        assert properties["Vmin"].shape == (8, 3, 1, 2)
        assert properties["Vmax"].shape == (8, 3, 1, 2)
        print(properties)
        expected = {
            "Bmh_km2": [0.0004, 0.0004, 0.0019, 0.0009, 0.0028, 0.0001, 0.0001, 0.0002],
            "Relief_m": [64.0, 53.0, 115.0, 105.0, 128.0, 110.0, 123.0, 121.0],
            "V": np.array(
                [
                    [54.78100096, 65.85638976, 77.78475303],
                    [49.886864, 59.97277709, 70.83545988],
                    [136.77950639, 164.43300279, 194.21624171],
                    [98.23690049, 118.09801744, 139.48874442],
                    [169.80542023, 204.13595482, 241.11046609],
                    [45.95804746, 55.24964921, 65.25684651],
                    [49.7021013, 59.75065986, 70.57311124],
                    [63.04258504, 75.78826562, 89.51555871],
                ]
            ).reshape(8, 3, 1),
            "Vmin": np.array(
                [
                    [
                        [9.90159311, 7.13477626],
                        [11.90345491, 8.57725485],
                        [14.05949071, 10.13082637],
                    ],
                    [
                        [9.01698436, 6.49735504],
                        [10.83999974, 7.81096254],
                        [12.80341522, 9.22573791],
                    ],
                    [
                        [24.72271397, 17.81440933],
                        [29.72104668, 21.41605053],
                        [35.10432753, 25.29507322],
                    ],
                    [
                        [17.75618918, 12.7945509],
                        [21.34605967, 15.38129856],
                        [25.21240514, 18.16726538],
                    ],
                    [
                        [30.69210399, 22.11576385],
                        [36.89730249, 26.58703453],
                        [43.58039625, 31.40266149],
                    ],
                    [
                        [8.30685599, 5.9856589],
                        [9.98630065, 7.19581385],
                        [11.79508826, 8.49916926],
                    ],
                    [
                        [8.98358874, 6.47329122],
                        [10.79985235, 7.78203359],
                        [12.75599605, 9.19156915],
                    ],
                    [
                        [11.39486345, 8.21077985],
                        [13.69862827, 9.87080025],
                        [16.17981825, 11.65866764],
                    ],
                ]
            ).reshape(8, 3, 1, 2),
            "Vmax": np.array(
                [
                    [
                        [303.07830611, 420.60997538],
                        [364.35338354, 505.6471037],
                        [430.34757989, 597.23339261],
                    ],
                    [
                        [276.00127733, 383.03266227],
                        [331.80203673, 460.47256993],
                        [391.90030878, 543.87653588],
                    ],
                    [
                        [756.73865719, 1050.19667048],
                        [909.73284673, 1262.52094774],
                        [1074.50993082, 1491.19744449],
                    ],
                    [
                        [543.49998857, 754.26552216],
                        [653.38249488, 906.75970383],
                        [771.72763618, 1070.99827178],
                    ],
                    [
                        [939.45598339, 1303.77051105],
                        [1129.39118152, 1567.36126434],
                        [1333.95429734, 1851.25254053],
                    ],
                    [
                        [254.26492639, 352.86710488],
                        [305.6711232, 424.20826899],
                        [361.03638405, 501.04379478],
                    ],
                    [
                        [274.97906952, 381.61404935],
                        [330.57316332, 458.7671479],
                        [390.44885333, 541.86221606],
                    ],
                    [
                        [348.78588473, 484.04263661],
                        [419.30192518, 581.90430945],
                        [495.24878016, 687.30282911],
                    ],
                ]
            ).reshape(8, 3, 1, 2),
        }
        for key, values in expected.items():
            assert np.allclose(properties[key], values)
        logcheck.check(
            [
                ("INFO", "Estimating potential sediment volume"),
                (
                    "DEBUG",
                    "    Computing catchment area burned at moderate-or-high severity",
                ),
                ("DEBUG", "    Computing vertical relief"),
                ("DEBUG", "    Running model"),
            ]
        )

    def test_keepdims(_, config, segments, rasters, logcheck):
        properties = {}
        config["I15_mm_hr"] = config["I15_mm_hr"][0:1]
        config["volume_CI"] = config["volume_CI"][0:1]
        _model._volume(config, segments, rasters, properties, logcheck.log)
        assert list(properties.keys()) == ["Bmh_km2", "Relief_m", "V", "Vmin", "Vmax"]
        assert properties["V"].shape == (8, 1, 1)
        assert properties["Vmin"].shape == (8, 1, 1, 1)
        assert properties["Vmax"].shape == (8, 1, 1, 1)

        expected = {
            "Bmh_km2": [0.0004, 0.0004, 0.0019, 0.0009, 0.0028, 0.0001, 0.0001, 0.0002],
            "Relief_m": [64.0, 53.0, 115.0, 105.0, 128.0, 110.0, 123.0, 121.0],
            "V": np.array(
                [
                    54.78100096,
                    49.886864,
                    136.77950639,
                    98.23690049,
                    169.80542023,
                    45.95804746,
                    49.7021013,
                    63.04258504,
                ]
            ).reshape(8, 1, 1),
            "Vmin": np.array(
                [
                    9.90159311,
                    9.01698436,
                    24.72271397,
                    17.75618918,
                    30.69210399,
                    8.30685599,
                    8.98358874,
                    11.39486345,
                ]
            ).reshape(8, 1, 1, 1),
            "Vmax": np.array(
                [
                    303.07830611,
                    276.00127733,
                    756.73865719,
                    543.49998857,
                    939.45598339,
                    254.26492639,
                    274.97906952,
                    348.78588473,
                ]
            ).reshape(8, 1, 1, 1),
        }
        for key, values in expected.items():
            assert np.allclose(properties[key], values)
        logcheck.check(
            [
                ("INFO", "Estimating potential sediment volume"),
                (
                    "DEBUG",
                    "    Computing catchment area burned at moderate-or-high severity",
                ),
                ("DEBUG", "    Computing vertical relief"),
                ("DEBUG", "    Running model"),
            ]
        )


class TestHazard:
    def test(_, i15_preresults, logcheck):
        props = i15_preresults
        assert "hazard" not in props
        _model._hazard(props, logcheck.log)
        assert "hazard" in props
        assert props["hazard"].shape == (8, 3, 1)
        expected = np.array(
            [
                [1.0, 1.0, 1.0],
                [1.0, 1.0, 2.0],
                [1.0, 2.0, 2.0],
                [1.0, 2.0, 2.0],
                [1.0, 2.0, 2.0],
                [1.0, 1.0, 1.0],
                [1.0, 1.0, 1.0],
                [1.0, 1.0, 1.0],
            ]
        ).reshape(8, 3, 1)
        assert np.array_equal(props["hazard"], expected)
        logcheck.check([("INFO", "Classifying combined hazard")])


class TestI15Hazard:
    def test_no_i15(_, logcheck):
        config = {"I15_mm_hr": []}
        properties = {}
        _model.i15_hazard(config, None, None, properties, logcheck.log)
        assert properties == {}
        logcheck.check([])

    def test(_, config, segments, rasters, slope23, logcheck):
        rasters["slopes"] = slope23
        properties = {}
        _model.i15_hazard(config, segments, rasters, properties, logcheck.log)
        for field in [
            "Terrain_M1",
            "Fire_M1",
            "Soil_M1",
            "likelihood",
            "Bmh_km2",
            "Relief_m",
            "V",
            "Vmin",
            "Vmax",
            "hazard",
        ]:
            assert field in properties

        expected = {
            "Terrain_M1": [
                0.25,
                0.36363636,
                0.3902439,
                0.2962963,
                0.32,
                0.2,
                0.0,
                0.0625,
            ],
            "Fire_M1": [
                0.2125,
                0.39972727,
                0.33404878,
                0.31096296,
                0.30389333,
                0.24,
                0.23333333,
                0.23125,
            ],
            "Soil_M1": [
                0.2,
                0.2,
                0.51034483,
                0.53333333,
                0.48571429,
                0.4,
                0.31111111,
                0.325,
            ],
            "likelihood": np.array(
                [
                    [
                        [0.11002361, 0.15373203, 0.21069354],
                        [0.19744073, 0.30038628, 0.42835867],
                        [0.33944157, 0.5188087, 0.69345555],
                        [0.30632435, 0.47148099, 0.64312649],
                        [0.28276936, 0.43635774, 0.60320832],
                        [0.17670979, 0.26580728, 0.37914002],
                        [0.10587792, 0.14685993, 0.20015381],
                        [0.11943936, 0.16942787, 0.23476014],
                    ]
                ]
            ).reshape(8, 3, 1),
            "Bmh_km2": [0.0004, 0.0004, 0.0019, 0.0009, 0.0028, 0.0001, 0.0001, 0.0002],
            "Relief_m": [64.0, 53.0, 115.0, 105.0, 128.0, 110.0, 123.0, 121.0],
            "V": np.array(
                [
                    [54.78100096, 65.85638976, 77.78475303],
                    [49.886864, 59.97277709, 70.83545988],
                    [136.77950639, 164.43300279, 194.21624171],
                    [98.23690049, 118.09801744, 139.48874442],
                    [169.80542023, 204.13595482, 241.11046609],
                    [45.95804746, 55.24964921, 65.25684651],
                    [49.7021013, 59.75065986, 70.57311124],
                    [63.04258504, 75.78826562, 89.51555871],
                ]
            ).reshape(8, 3, 1),
            "Vmin": np.array(
                [
                    [
                        [9.90159311, 7.13477626],
                        [11.90345491, 8.57725485],
                        [14.05949071, 10.13082637],
                    ],
                    [
                        [9.01698436, 6.49735504],
                        [10.83999974, 7.81096254],
                        [12.80341522, 9.22573791],
                    ],
                    [
                        [24.72271397, 17.81440933],
                        [29.72104668, 21.41605053],
                        [35.10432753, 25.29507322],
                    ],
                    [
                        [17.75618918, 12.7945509],
                        [21.34605967, 15.38129856],
                        [25.21240514, 18.16726538],
                    ],
                    [
                        [30.69210399, 22.11576385],
                        [36.89730249, 26.58703453],
                        [43.58039625, 31.40266149],
                    ],
                    [
                        [8.30685599, 5.9856589],
                        [9.98630065, 7.19581385],
                        [11.79508826, 8.49916926],
                    ],
                    [
                        [8.98358874, 6.47329122],
                        [10.79985235, 7.78203359],
                        [12.75599605, 9.19156915],
                    ],
                    [
                        [11.39486345, 8.21077985],
                        [13.69862827, 9.87080025],
                        [16.17981825, 11.65866764],
                    ],
                ]
            ).reshape(8, 3, 1, 2),
            "Vmax": np.array(
                [
                    [
                        [303.07830611, 420.60997538],
                        [364.35338354, 505.6471037],
                        [430.34757989, 597.23339261],
                    ],
                    [
                        [276.00127733, 383.03266227],
                        [331.80203673, 460.47256993],
                        [391.90030878, 543.87653588],
                    ],
                    [
                        [756.73865719, 1050.19667048],
                        [909.73284673, 1262.52094774],
                        [1074.50993082, 1491.19744449],
                    ],
                    [
                        [543.49998857, 754.26552216],
                        [653.38249488, 906.75970383],
                        [771.72763618, 1070.99827178],
                    ],
                    [
                        [939.45598339, 1303.77051105],
                        [1129.39118152, 1567.36126434],
                        [1333.95429734, 1851.25254053],
                    ],
                    [
                        [254.26492639, 352.86710488],
                        [305.6711232, 424.20826899],
                        [361.03638405, 501.04379478],
                    ],
                    [
                        [274.97906952, 381.61404935],
                        [330.57316332, 458.7671479],
                        [390.44885333, 541.86221606],
                    ],
                    [
                        [348.78588473, 484.04263661],
                        [419.30192518, 581.90430945],
                        [495.24878016, 687.30282911],
                    ],
                ]
            ).reshape(8, 3, 1, 2),
            "hazard": np.array(
                [
                    [1.0, 1.0, 1.0],
                    [1.0, 1.0, 2.0],
                    [1.0, 2.0, 2.0],
                    [1.0, 2.0, 2.0],
                    [1.0, 2.0, 2.0],
                    [1.0, 1.0, 1.0],
                    [1.0, 1.0, 1.0],
                    [1.0, 1.0, 1.0],
                ]
            ).reshape(8, 3, 1),
        }
        for field, values in expected.items():
            assert np.allclose(properties[field], values)
        logcheck.check(
            [
                ("INFO", "Estimating debris-flow likelihood"),
                ("DEBUG", "    Computing M1 variables"),
                ("DEBUG", "    Running model"),
                ("INFO", "Estimating potential sediment volume"),
                (
                    "DEBUG",
                    "    Computing catchment area burned at moderate-or-high severity",
                ),
                ("DEBUG", "    Computing vertical relief"),
                ("DEBUG", "    Running model"),
                ("INFO", "Classifying combined hazard"),
            ]
        )


def check_thresholds(props, expected, shape=(8, 2, 3)):
    for field, values in expected.items():
        assert field in props
        assert props[field].shape == shape
        print(props[field])
        print("-----")
        print(values)
        assert np.allclose(props[field], values)


class TestThresholds:
    @pytest.mark.parametrize("field", ("durations", "probabilities"))
    def test_missing(_, config, field, logcheck):
        config[field] = []
        properties = {}
        _model.thresholds(config, None, None, properties, logcheck.log)
        assert properties == {}
        logcheck.check([])

    def test(_, config, segments, m1_vars, thresholds, logcheck):
        props = m1_vars
        _model.thresholds(config, segments, None, props, logcheck.log)
        check_thresholds(props, thresholds)
        logcheck.check(
            [
                ("INFO", "Estimating rainfall thresholds"),
                ("DEBUG", "    Running model"),
            ]
        )

    def test_get_variables(_, config, segments, rasters, slope23, thresholds, logcheck):
        props = {}
        rasters["slopes"] = slope23
        _model.thresholds(config, segments, rasters, props, logcheck.log)
        check_thresholds(props, thresholds)
        for field in ["Terrain_M1", "Fire_M1", "Soil_M1"]:
            assert field in props
        logcheck.check(
            [
                ("INFO", "Estimating rainfall thresholds"),
                ("DEBUG", "    Computing M1 variables"),
                ("DEBUG", "    Running model"),
            ]
        )

    def test_keepdims(_, config, segments, rasters, m1_vars, logcheck):
        props = m1_vars
        config["durations"] = config["durations"][0:1]
        config["probabilities"] = config["probabilities"][0:1]
        _model.thresholds(config, segments, rasters, props, logcheck.log)
        shape = (8, 1, 1)
        expected = {
            "accumulations": np.array(
                [
                    [[9.43163365]],
                    [[6.51813013]],
                    [[4.89842804]],
                    [[5.16240969]],
                    [[5.37930364]],
                    [[6.94338179]],
                    [[9.7029997]],
                    [[8.89569612]],
                ]
            ),
            "intensities": np.array(
                [
                    [[37.72653459]],
                    [[26.07252052]],
                    [[19.59371217]],
                    [[20.64963877]],
                    [[21.51721456]],
                    [[27.77352716]],
                    [[38.81199881]],
                    [[35.5827845]],
                ]
            ),
        }
        check_thresholds(props, expected, shape)
        logcheck.check(
            [
                ("INFO", "Estimating rainfall thresholds"),
                ("DEBUG", "    Running model"),
            ]
        )
