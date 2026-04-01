File Formats
============

.. _vector-formats:

Vector Features
---------------

Wildcat supports the following vector feature file formats:

.. list-table::
    :header-rows: 1

    * - Format
      - Description
      - Extensions
    * - CSV
      - Comma Separated Value
      - ``.csv``
    * - DGN
      - Microstation DGN
      - ``.dgn``
    * - DXF
      - AutoCAD DXF
      - ``.dxf``
    * - FlatGeobuf
      - FlatGeobuf
      - ``.fgb``
    * - GML
      - Geography Markup Language
      - ``.gml``, ``.xml``
    * - GPKG
      - GeoPackage vector
      - ``.gpkg``
    * - GPX
      - GPS Exchange Format
      - ``.gpx``
    * - GeoJSON
      - GeoJSON
      - ``.json``, ``.geojson``
    * - GeoJSONSeq
      - Sequence of GeoJSON features
      - ``.geojsons``, ``.geojsonl``
    * - MapInfo File
      - MapInfo TAB and MIF/MID
      - ``.tab``, ``.mid``, ``.mif``
    * - OGR_GMT
      - GMT ASCII Vectors
      - ``.gmt``
    * - OpenFileGDB
      - ESRI File Geodatabase Vector
      - ``.gdb``
    * - Shapefile
      - ESRI Shapefile / DBF
      - ``.shp``, ``.dbf``, ``.shz``, ``.shp.zip``
    * - SQLite
      - SQLite / Spatialite RDBMS
      - ``.sqlite``, ``.db``

The values in the first column are the supported values of the :confval:`format` setting for the :doc:`export command </commands/export>`. Input vector datasets may use any of these formats. If the file path for an input vector dataset is missing an extension, then wildcat will scan the extensions in the third column for a matching file.

.. _raster-formats:

Rasters
-------

Wildcat supports the following raster file formats:

.. list-table::
    :header-rows: 1

    * - Format
      - Description
      - Extensions
    * - ADRG
      - ADRG/ARC Digitized Raster Graphics
      - ``.gen``
    * - BMP
      - Bitmap
      - ``.bmp``
    * - BT
      - VTP Binary Terrain Format
      - ``.bt``
    * - BYN
      - Natural Resources Canada's Geoid file format
      - ``.byn``, ``.err``
    * - EHdr
      - ESRI labelled hdr
      - ``.bil``
    * - ERS
      - ERMapper
      - ``.ers``
    * - GTiff
      - GeoTIFF File Format
      - ``.tif``, ``.tiff``
    * - HFA
      - Erdas Imagine
      - ``.img``
    * - ILWIS
      - Raster Map
      - ``.mpr``, ``.mpl``
    * - ISIS3
      - USGS Astrogeology ISIS Cube (Version 3)
      - ``.lbl``, ``.cub``
    * - KRO
      - KOLOR Raw Format
      - ``.kro``
    * - MFF
      - Vexcel MFF Raster
      - ``.hdr``
    * - NITF
      - National Imagery Transmission Format
      - ``.ntf``
    * - NTv2
      - NTv2 Datum Grid Shift
      - ``.gsb``, ``.gvb``
    * - NWT_GRD
      - Northwood/Verticall Mapper File Format
      - ``.grd``
    * - PCIDSK
      - PCD Geomatics Database File
      - ``.pix``
    * - PCRaster
      - PCRaster raster file format
      - ``.map``
    * - PDS4
      - NASA Planetary Data System (Version 4)
      - ``.xml``
    * - RMF
      - Raster Matrix Format
      - ``.rsw``
    * - SAGA
      - SAGA GIS Binary Grid File Format
      - ``.sdat``, ``.sg-grd-z``
    * - Terragen
      - Terragen Terrain File
      - ``.ter``
    * - USGSDEM
      - USGS ASCII DEM (and CDED)
      - ``.dem``
    * - VRT
      - GDAL Virtual Format
      - ``.vrt``

Input raster datasets may use any of these formats. If the file path for an input raster dataset is missing an extension, then wildcat will scan the extensions in the third column for a matching file.