import pandas as pd
import io

# Load the file content
recipes_content = """product_id,Product,Price,Type,Product Note,item_id,Ingredient,Note,Qty
1001,1 Rose Dozen Red Standard,129,Standard,,207,Roses Red,,12
1001,1 Rose Dozen Red Standard,129,Standard,,,Greenery,Generic,1
1001,1 Rose Dozen Red Standard,129,Standard,,168,Vase Jordan Red,,1
1002,1 Rose Dozen Red Deluxe,140,Deluxe,,207,Roses Red,,12
1002,1 Rose Dozen Red Deluxe,140,Deluxe,,,Greenery,Generic,1
1002,1 Rose Dozen Red Deluxe,140,Deluxe,,,Filler,Generic,1
1002,1 Rose Dozen Red Deluxe,140,Deluxe,,168,Vase Jordan Red,,1
1003,1 Rose Dozen Red Premium,160,Premium,,207,Roses Red,,12
1003,1 Rose Dozen Red Premium,160,Premium,,,Greenery,Generic,1
1003,1 Rose Dozen Red Premium,160,Premium,,,Filler,Generic,1
1003,1 Rose Dozen Red Premium,160,Premium,,198,Lily Asiatic,,3
1003,1 Rose Dozen Red Premium,160,Premium,,168,Vase Jordan Red,,1
1004,1 Rose Dozen Yellow Standard,129,Standard,Match Color,210,Roses Yellow,,12
1004,1 Rose Dozen Yellow Standard,129,Standard,Match Color,,Greenery,Generic,1
1004,1 Rose Dozen Yellow Standard,129,Standard,Match Color,169,Vase Jordan Silver,,1
1005,1 Rose Dozen Yellow Deluxe,140,Deluxe,Match Color,210,Roses Yellow,,12
1005,1 Rose Dozen Yellow Deluxe,140,Deluxe,Match Color,,Greenery,Generic,1
1005,1 Rose Dozen Yellow Deluxe,140,Deluxe,Match Color,,Filler,Generic,1
1005,1 Rose Dozen Yellow Deluxe,140,Deluxe,Match Color,169,Vase Jordan Silver,,1
1006,1 Rose Dozen Yellow Premium,160,Premium,Match Color,210,Roses Yellow,,12
1006,1 Rose Dozen Yellow Premium,160,Premium,Match Color,,Greenery,Generic,1
1006,1 Rose Dozen Yellow Premium,160,Premium,Match Color,,Filler,Generic,1
1006,1 Rose Dozen Yellow Premium,160,Premium,Match Color,198,Lily Asiatic,,3
1006,1 Rose Dozen Yellow Premium,160,Premium,Match Color,169,Vase Jordan Silver,,1
1007,1 Rose Dozen Pink Standard,129,Standard,,206,Roses Pink,,12
1007,1 Rose Dozen Pink Standard,129,Standard,,,Greenery,Generic,1
1007,1 Rose Dozen Pink Standard,129,Standard,,167,Vase Jordan Pink,,1
1008,1 Rose Dozen Pink Deluxe,140,Deluxe,,206,Roses Pink,,12
1008,1 Rose Dozen Pink Deluxe,140,Deluxe,,,Greenery,Generic,1
1008,1 Rose Dozen Pink Deluxe,140,Deluxe,,,Filler,Generic,1
1008,1 Rose Dozen Pink Deluxe,140,Deluxe,,167,Vase Jordan Pink,,1
1009,1 Rose Dozen Pink Premium,160,Premium,,206,Roses Pink,,12
1009,1 Rose Dozen Pink Premium,160,Premium,,,Greenery,Generic,1
1009,1 Rose Dozen Pink Premium,160,Premium,,,Filler,Generic,1
1009,1 Rose Dozen Pink Premium,160,Premium,,198,Lily Asiatic,,3
1009,1 Rose Dozen Pink Premium,160,Premium,,167,Vase Jordan Pink,,1
1010,1 Rose Dozen Lavender Standard,129,Standard,Match Color,205,Roses Lavender,,12
1010,1 Rose Dozen Lavender Standard,129,Standard,Match Color,,Greenery,Generic,1
1010,1 Rose Dozen Lavender Standard,129,Standard,Match Color,169,Vase Jordan Silver,,1
1011,1 Rose Dozen Lavender Deluxe,140,Deluxe,Match Color,205,Roses Lavender,,12
1011,1 Rose Dozen Lavender Deluxe,140,Deluxe,Match Color,,Greenery,Generic,1
1011,1 Rose Dozen Lavender Deluxe,140,Deluxe,Match Color,,Filler,Generic,1
1011,1 Rose Dozen Lavender Deluxe,140,Deluxe,Match Color,169,Vase Jordan Silver,,1
1012,1 Rose Dozen Lavender Premium,160,Premium,Match Color,205,Roses Lavender,,12
1012,1 Rose Dozen Lavender Premium,160,Premium,Match Color,,Greenery,Generic,1
1012,1 Rose Dozen Lavender Premium,160,Premium,Match Color,,Filler,Generic,1
1012,1 Rose Dozen Lavender Premium,160,Premium,Match Color,198,Lily Asiatic,,3
1012,1 Rose Dozen Lavender Premium,160,Premium,Match Color,169,Vase Jordan Silver,,1
1013,1 Rose Dozen White Standard,129,Standard,Match Color,209,Roses White,,12
1013,1 Rose Dozen White Standard,129,Standard,Match Color,,Greenery,Generic,1
1013,1 Rose Dozen White Standard,129,Standard,Match Color,169,Vase Jordan Silver,,1
1014,1 Rose Dozen White Deluxe,140,Deluxe,Match Color,209,Roses White,,12
1014,1 Rose Dozen White Deluxe,140,Deluxe,Match Color,,Greenery,Generic,1
1014,1 Rose Dozen White Deluxe,140,Deluxe,Match Color,,Filler,Generic,1
1014,1 Rose Dozen White Deluxe,140,Deluxe,Match Color,169,Vase Jordan Silver,,1
1015,1 Rose Dozen White Premium,160,Premium,Match Color,209,Roses White,,12
1015,1 Rose Dozen White Premium,160,Premium,Match Color,,Greenery,Generic,1
1015,1 Rose Dozen White Premium,160,Premium,Match Color,,Filler,Generic,1
1015,1 Rose Dozen White Premium,160,Premium,Match Color,198,Lily Asiatic,,3
1015,1 Rose Dozen White Premium,160,Premium,Match Color,169,Vase Jordan Silver,,1
1016,1 Rose Dozen Orange Standard,129,Standard,Match Color,224,Roses Orange,,12
1016,1 Rose Dozen Orange Standard,129,Standard,Match Color,,Greenery,Generic,1
1016,1 Rose Dozen Orange Standard,129,Standard,Match Color,169,Vase Jordan Silver,,1
1017,1 Rose Dozen Orange Deluxe,140,Deluxe,Match Color,224,Roses Orange,,12
1017,1 Rose Dozen Orange Deluxe,140,Deluxe,Match Color,,Greenery,Generic,1
1017,1 Rose Dozen Orange Deluxe,140,Deluxe,Match Color,,Filler,Generic,1
1017,1 Rose Dozen Orange Deluxe,140,Deluxe,Match Color,169,Vase Jordan Silver,,1
1018,1 Rose Dozen Orange Premium,160,Premium,Match Color,224,Roses Orange,,12
1018,1 Rose Dozen Orange Premium,160,Premium,Match Color,,Greenery,Generic,1
1018,1 Rose Dozen Orange Premium,160,Premium,Match Color,,Filler,Generic,1
1018,1 Rose Dozen Orange Premium,160,Premium,Match Color,198,Lily Asiatic,,3
1018,1 Rose Dozen Orange Premium,160,Premium,Match Color,169,Vase Jordan Silver,,1
1019,1 Rose Dozen Bicolor Standard,129,Standard,Match Color,225,Roses Bicolor,,12
1019,1 Rose Dozen Bicolor Standard,129,Standard,Match Color,,Greenery,Generic,1
1019,1 Rose Dozen Bicolor Standard,129,Standard,Match Color,169,Vase Jordan Silver,,1
1020,1 Rose Dozen Bicolor Deluxe,140,Deluxe,Match Color,225,Roses Bicolor,,12
1020,1 Rose Dozen Bicolor Deluxe,140,Deluxe,Match Color,,Greenery,Generic,1
1020,1 Rose Dozen Bicolor Deluxe,140,Deluxe,Match Color,,Filler,Generic,1
1020,1 Rose Dozen Bicolor Deluxe,140,Deluxe,Match Color,169,Vase Jordan Silver,,1
1021,1 Rose Dozen Bicolor Premium,160,Premium,Match Color,225,Roses Bicolor,,12
1021,1 Rose Dozen Bicolor Premium,160,Premium,Match Color,,Greenery,Generic,1
1021,1 Rose Dozen Bicolor Premium,160,Premium,Match Color,,Filler,Generic,1
1021,1 Rose Dozen Bicolor Premium,160,Premium,Match Color,198,Lily Asiatic,,3
1021,1 Rose Dozen Bicolor Premium,160,Premium,Match Color,169,Vase Jordan Silver,,1
1022,1 Rose Dozen Aggie Standard,129,Standard,Match Color,226,Roses Aggie,,12
1022,1 Rose Dozen Aggie Standard,129,Standard,Match Color,,Greenery,Generic,1
1022,1 Rose Dozen Aggie Standard,129,Standard,Match Color,169,Vase Jordan Silver,,1
1023,1 Rose Dozen Aggie Deluxe,140,Deluxe,Match Color,226,Roses Aggie,,12
1023,1 Rose Dozen Aggie Deluxe,140,Deluxe,Match Color,,Greenery,Generic,1
1023,1 Rose Dozen Aggie Deluxe,140,Deluxe,Match Color,,Filler,Generic,1
1023,1 Rose Dozen Aggie Deluxe,140,Deluxe,Match Color,169,Vase Jordan Silver,,1
1024,1 Rose Dozen Aggie Premium,160,Premium,Match Color,226,Roses Aggie,,12
1024,1 Rose Dozen Aggie Premium,160,Premium,Match Color,,Greenery,Generic,1
1024,1 Rose Dozen Aggie Premium,160,Premium,Match Color,,Filler,Generic,1
1024,1 Rose Dozen Aggie Premium,160,Premium,Match Color,198,Lily Asiatic,,3
1024,1 Rose Dozen Aggie Premium,160,Premium,Match Color,169,Vase Jordan Silver,,1
1025,1 Rose Dozen Mix Standard,129,Standard,Match Color,,Roses Mix,Generic,12
1025,1 Rose Dozen Mix Standard,129,Standard,Match Color,,Greenery,Generic,1
1025,1 Rose Dozen Mix Standard,129,Standard,Match Color,169,Vase Jordan Silver,,1
1026,1 Rose Dozen Mix Deluxe,140,Deluxe,Match Color,,Roses Mix,Generic,12
1026,1 Rose Dozen Mix Deluxe,140,Deluxe,Match Color,,Greenery,Generic,1
1026,1 Rose Dozen Mix Deluxe,140,Deluxe,Match Color,,Filler,Generic,1
1026,1 Rose Dozen Mix Deluxe,140,Deluxe,Match Color,169,Vase Jordan Silver,,1
1027,1 Rose Dozen Mix Premium,160,Premium,Match Color,,Roses Mix,Generic,12
1027,1 Rose Dozen Mix Premium,160,Premium,Match Color,,Greenery,Generic,1
1027,1 Rose Dozen Mix Premium,160,Premium,Match Color,,Filler,Generic,1
1027,1 Rose Dozen Mix Premium,160,Premium,Match Color,198,Lily Asiatic,,3
1027,1 Rose Dozen Mix Premium,160,Premium,Match Color,169,Vase Jordan Silver,,1
1028,Rose Half Dozen Red Standard,60,Standard,,207,Roses Red,,6
1028,Rose Half Dozen Red Standard,60,Standard,,,Filler,Generic,1
1028,Rose Half Dozen Red Standard,60,Standard,,150,Hurricane,,1
1029,Rose Half Dozen Red Deluxe,80,Deluxe,,207,Roses Red,,6
1029,Rose Half Dozen Red Deluxe,80,Deluxe,,,Filler,Generic,1
1029,Rose Half Dozen Red Deluxe,80,Deluxe,,198,Lily Asiatic,,3
1029,Rose Half Dozen Red Deluxe,80,Deluxe,,150,Hurricane,,1
1030,Rose Half Dozen Yellow Standard,60,Standard,,210,Roses Yellow,,6
1030,Rose Half Dozen Yellow Standard,60,Standard,,,Filler,Generic,1
1030,Rose Half Dozen Yellow Standard,60,Standard,,150,Hurricane,,1
1031,Rose Half Dozen Yellow Deluxe,80,Deluxe,,210,Roses Yellow,,6
1031,Rose Half Dozen Yellow Deluxe,80,Deluxe,,,Filler,Generic,1
1031,Rose Half Dozen Yellow Deluxe,80,Deluxe,,198,Lily Asiatic,,3
1031,Rose Half Dozen Yellow Deluxe,80,Deluxe,,150,Hurricane,,1
1032,Rose Half Dozen Pink Standard,60,Standard,,206,Roses Pink,,6
1032,Rose Half Dozen Pink Standard,60,Standard,,,Filler,Generic,1
1032,Rose Half Dozen Pink Standard,60,Standard,,150,Hurricane,,1
1033,Rose Half Dozen Pink Deluxe,80,Deluxe,,206,Roses Pink,,6
1033,Rose Half Dozen Pink Deluxe,80,Deluxe,,,Filler,Generic,1
1033,Rose Half Dozen Pink Deluxe,80,Deluxe,,198,Lily Asiatic,,3
1033,Rose Half Dozen Pink Deluxe,80,Deluxe,,150,Hurricane,,1
1034,Rose Half Dozen Lavender Standard,60,Standard,,205,Roses Lavender,,6
1034,Rose Half Dozen Lavender Standard,60,Standard,,,Filler,Generic,1
1034,Rose Half Dozen Lavender Standard,60,Standard,,150,Hurricane,,1
1035,Rose Half Dozen Lavender Deluxe,80,Deluxe,,205,Roses Lavender,,6
1035,Rose Half Dozen Lavender Deluxe,80,Deluxe,,,Filler,Generic,1
1035,Rose Half Dozen Lavender Deluxe,80,Deluxe,,198,Lily Asiatic,,3
1035,Rose Half Dozen Lavender Deluxe,80,Deluxe,,150,Hurricane,,1
1036,Rose Half Dozen White Standard,60,Standard,,209,Roses White,,6
1036,Rose Half Dozen White Standard,60,Standard,,,Filler,Generic,1
1036,Rose Half Dozen White Standard,60,Standard,,150,Hurricane,,1
1037,Rose Half Dozen White Deluxe,80,Deluxe,,209,Roses White,,6
1037,Rose Half Dozen White Deluxe,80,Deluxe,,,Filler,Generic,1
1037,Rose Half Dozen White Deluxe,80,Deluxe,,198,Lily Asiatic,,3
1037,Rose Half Dozen White Deluxe,80,Deluxe,,150,Hurricane,,1
1038,Rose Half Dozen Orange Standard,60,Standard,,224,Roses Orange,,6
1038,Rose Half Dozen Orange Standard,60,Standard,,,Filler,Generic,1
1038,Rose Half Dozen Orange Standard,60,Standard,,150,Hurricane,,1
1039,Rose Half Dozen Orange Deluxe,80,Deluxe,,224,Roses Orange,,6
1039,Rose Half Dozen Orange Deluxe,80,Deluxe,,,Filler,Generic,1
1039,Rose Half Dozen Orange Deluxe,80,Deluxe,,198,Lily Asiatic,,3
1039,Rose Half Dozen Orange Deluxe,80,Deluxe,,150,Hurricane,,1
1040,18 Roses Red Standard,165,Standard,,207,Roses Red,,18
1040,18 Roses Red Standard,165,Standard,,,Greenery,Generic,1
1041,18 Roses Red Deluxe,180,Deluxe,,207,Roses Red,,18
1041,18 Roses Red Deluxe,180,Deluxe,,,Greenery,Generic,1
1041,18 Roses Red Deluxe,180,Deluxe,,,Filler,Generic,1
1042,18 Roses Red Premium,216,Premium,,207,Roses Red,,18
1042,18 Roses Red Premium,216,Premium,,,Greenery,Generic,1
1042,18 Roses Red Premium,216,Premium,,,Filler,Generic,1
1042,18 Roses Red Premium,216,Premium,,198,Lily Asiatic,,3
1043,18 Roses Yellow Standard,165,Standard,,210,Roses Yellow,,18
1043,18 Roses Yellow Standard,165,Standard,,,Greenery,Generic,1
1044,18 Roses Yellow Deluxe,180,Deluxe,,210,Roses Yellow,,18
1044,18 Roses Yellow Deluxe,180,Deluxe,,,Greenery,Generic,1
1044,18 Roses Yellow Deluxe,180,Deluxe,,,Filler,Generic,1
1045,18 Roses Yellow Premium,216,Premium,,210,Roses Yellow,,18
1045,18 Roses Yellow Premium,216,Premium,,,Greenery,Generic,1
1045,18 Roses Yellow Premium,216,Premium,,,Filler,Generic,1
1045,18 Roses Yellow Premium,216,Premium,,198,Lily Asiatic,,3
1046,18 Roses Pink Standard,165,Standard,,206,Roses Pink,,18
1046,18 Roses Pink Standard,165,Standard,,,Greenery,Generic,1
1047,18 Roses Pink Deluxe,180,Deluxe,,206,Roses Pink,,18
1047,18 Roses Pink Deluxe,180,Deluxe,,,Greenery,Generic,1
1047,18 Roses Pink Deluxe,180,Deluxe,,,Filler,Generic,1
1048,18 Roses Pink Premium,216,Premium,,206,Roses Pink,,18
1048,18 Roses Pink Premium,216,Premium,,,Greenery,Generic,1
1048,18 Roses Pink Premium,216,Premium,,,Filler,Generic,1
1048,18 Roses Pink Premium,216,Premium,,198,Lily Asiatic,,3
1049,18 Roses Lavender Standard,165,Standard,,205,Roses Lavender,,18
1049,18 Roses Lavender Standard,165,Standard,,,Greenery,Generic,1
1050,18 Roses Lavender Deluxe,180,Deluxe,,205,Roses Lavender,,18
1050,18 Roses Lavender Deluxe,180,Deluxe,,,Greenery,Generic,1
1050,18 Roses Lavender Deluxe,180,Deluxe,,,Filler,Generic,1
1051,18 Roses Lavender Premium,216,Premium,,205,Roses Lavender,,18
1051,18 Roses Lavender Premium,216,Premium,,,Greenery,Generic,1
1051,18 Roses Lavender Premium,216,Premium,,,Filler,Generic,1
1051,18 Roses Lavender Premium,216,Premium,,198,Lily Asiatic,,3
1052,18 Roses White Standard,165,Standard,,209,Roses White,,18
1052,18 Roses White Standard,165,Standard,,,Greenery,Generic,1
1053,18 Roses White Deluxe,180,Deluxe,,209,Roses White,,18
1053,18 Roses White Deluxe,180,Deluxe,,,Greenery,Generic,1
1053,18 Roses White Deluxe,180,Deluxe,,,Filler,Generic,1
1054,18 Roses White Premium,216,Premium,,209,Roses White,,18
1054,18 Roses White Premium,216,Premium,,,Greenery,Generic,1
1054,18 Roses White Premium,216,Premium,,,Filler,Generic,1
1054,18 Roses White Premium,216,Premium,,198,Lily Asiatic,,3
1055,18 Roses Orange Standard,165,Standard,,224,Roses Orange,,18
1055,18 Roses Orange Standard,165,Standard,,,Greenery,Generic,1
1056,18 Roses Orange Deluxe,180,Deluxe,,224,Roses Orange,,18
1056,18 Roses Orange Deluxe,180,Deluxe,,,Greenery,Generic,1
1056,18 Roses Orange Deluxe,180,Deluxe,,,Filler,Generic,1
1057,18 Roses Orange Premium,216,Premium,,224,Roses Orange,,18
1057,18 Roses Orange Premium,216,Premium,,,Greenery,Generic,1
1057,18 Roses Orange Premium,216,Premium,,,Filler,Generic,1
1057,18 Roses Orange Premium,216,Premium,,198,Lily Asiatic,,3
1058,Color Me Yours Standard,85,Standard,,208,Roses Spray,,12
1058,Color Me Yours Standard,85,Standard,,,Greenery,Generic,1
1059,Color Me Yours Standard,85,Standard,,,Roses Mix,Generic,12
1059,Color Me Yours Standard,85,Standard,,,Greenery,Generic,1
1059,Color Me Yours Standard,85,Standard,,159,Vase Smoky,,1
1060,Color Me Yours Deluxe,99,Deluxe,,,Roses Mix,Generic,12
1060,Color Me Yours Deluxe,99,Deluxe,,,Greenery,Generic,2
1060,Color Me Yours Deluxe,99,Deluxe,,,Filler,Generic,1
1060,Color Me Yours Deluxe,99,Deluxe,,159,Vase Smoky,,1
1061,Color Me Yours Premium,120,Premium,,,Roses Mix,Generic,12
1061,Color Me Yours Premium,120,Premium,,,Greenery,Generic,2
1061,Color Me Yours Premium,120,Premium,,,Filler,Generic,1
1061,Color Me Yours Premium,120,Premium,,198,Lily Asiatic,,3
1061,Color Me Yours Premium,120,Premium,,159,Vase Smoky,,1
1062,Dozen Roses Wrapped Standard,90,Standard,,207,Roses Red,,12
1062,Dozen Roses Wrapped Standard,90,Standard,,,Greenery,Generic,2
1062,Dozen Roses Wrapped Standard,90,Standard,,,Filler,Generic,1
1062,Dozen Roses Wrapped Standard,90,Standard,,222,Wrap,,1
1063,Dozen Roses Wrapped Deluxe,105,Deluxe,Premium Blooms?,207,Roses Red,,12
1063,Dozen Roses Wrapped Deluxe,105,Deluxe,Premium Blooms?,,Greenery,Generic,2
1063,Dozen Roses Wrapped Deluxe,105,Deluxe,Premium Blooms?,,Filler,Generic,1
1063,Dozen Roses Wrapped Deluxe,105,Deluxe,Premium Blooms?,222,Wrap,,1
1064,Dozen Roses Wrapped Premium,125,Premium,,207,Roses Red,,12
1064,Dozen Roses Wrapped Premium,125,Premium,,,Greenery,Generic,2
1064,Dozen Roses Wrapped Premium,125,Premium,,,Filler,Generic,1
1064,Dozen Roses Wrapped Premium,125,Premium,,198,Lily Asiatic,,3
1064,Dozen Roses Wrapped Premium,125,Premium,,222,Wrap,,1
1065,Remember When Standard,135,Standard,,207,Roses Red,,4
1065,Remember When Standard,135,Standard,,184,Cremons,,4
1065,Remember When Standard,135,Standard,,198,Lily Asiatic,,2
1065,Remember When Standard,135,Standard,,178,Alstro,,6
1065,Remember When Standard,135,Standard,,175,Vase Gathering Pink,,1
1066,Remember When Deluxe,170,Deluxe,,207,Roses Red,,6
1066,Remember When Deluxe,170,Deluxe,,184,Cremons,,6
1066,Remember When Deluxe,170,Deluxe,,198,Lily Asiatic,,3
1066,Remember When Deluxe,170,Deluxe,,178,Alstro,,9
1066,Remember When Deluxe,170,Deluxe,,175,Vase Gathering Pink,,1
1067,Never Ending Love Standard,160,Standard,,198,Lily Asiatic,,3
1067,Never Ending Love Standard,160,Standard,,206,Roses Pink,,6
1067,Never Ending Love Standard,160,Standard,,182,Carns,,5
1067,Never Ending Love Standard,160,Standard,,189,Dianthus,,5
1067,Never Ending Love Standard,160,Standard,,167,Vase Jordan Pink,,1
1068,Never Ending Love Deluxe,190,Deluxe,,198,Lily Asiatic,,4
1068,Never Ending Love Deluxe,190,Deluxe,,206,Roses Pink,,9
1068,Never Ending Love Deluxe,190,Deluxe,,182,Carns,,7
1068,Never Ending Love Deluxe,190,Deluxe,,,Daisies,Generic,7
1068,Never Ending Love Deluxe,190,Deluxe,,167,Vase Jordan Pink,,1
1069,Smitten Standard,155,Standard,,199,Lily Oriental,,2
1069,Smitten Standard,155,Standard,,206,Roses Pink,,6
1069,Smitten Standard,155,Standard,,216,Stock,,4
1069,Smitten Standard,155,Standard,,220,Wax,,2
1069,Smitten Standard,155,Standard,,169,Vase Jordan Silver,,1
1070,Smitten Deluxe,180,Deluxe,,199,Lily Oriental,,3
1070,Smitten Deluxe,180,Deluxe,,206,Roses Pink,,8
1070,Smitten Deluxe,180,Deluxe,,216,Stock,,4
1070,Smitten Deluxe,180,Deluxe,,220,Wax,,2
1070,Smitten Deluxe,180,Deluxe,,169,Vase Jordan Silver,,1
1071,Smitten Premium,215,Premium,,199,Lily Oriental,,4
1071,Smitten Premium,215,Premium,,206,Roses Pink,,12
1071,Smitten Premium,215,Premium,,216,Stock,,4
1071,Smitten Premium,215,Premium,,220,Wax,,2
1071,Smitten Premium,215,Premium,,169,Vase Jordan Silver,,1
1072,Tulip Mania Standard,125,Standard,,218,Tulips,,10
1072,Tulip Mania Standard,125,Standard,,216,Stock,,4
1072,Tulip Mania Standard,125,Standard,,220,Wax,,2
1072,Tulip Mania Standard,125,Standard,,162,Vase Milk Jug,,1
1073,Kissed by the Sun Standard,125,Standard,,218,Tulips,,4
1073,Kissed by the Sun Standard,125,Standard,,217,Sunflowers,,1
1073,Kissed by the Sun Standard,125,Standard,,207,Roses Red,,5
1073,Kissed by the Sun Standard,125,Standard,,188,Green Ball,,3
1073,Kissed by the Sun Standard,125,Standard,,215,Statice,,2
1073,Kissed by the Sun Standard,125,Standard,,221,Raffia,,1
1073,Kissed by the Sun Standard,125,Standard,,176,Vase White Bowl,,1
1074,Wanted Red Standard,75,Standard,,182,Carns,,12
1074,Wanted Red Standard,75,Standard,,180,Baby Breath,,2
1074,Wanted Red Standard,75,Standard,,223,Bow,,1
1074,Wanted Red Standard,75,Standard,,153,Vase Red Square,,1
1075,Wanted Red Deluxe,100,Deluxe,,182,Carns,,6
1075,Wanted Red Deluxe,100,Deluxe,,207,Roses Red,,6
1075,Wanted Red Deluxe,100,Deluxe,,180,Baby Breath,,2
1075,Wanted Red Deluxe,100,Deluxe,,223,Bow,,1
1075,Wanted Red Deluxe,100,Deluxe,,153,Vase Red Square,,1
1076,Wanted Pink Standard,75,Standard,,182,Carns,,12
1076,Wanted Pink Standard,75,Standard,,180,Baby Breath,,2
1076,Wanted Pink Standard,75,Standard,,223,Bow,,1
1076,Wanted Pink Standard,75,Standard,,157,Vase Mauve,,1
1077,Wanted Pink Deluxe,100,Deluxe,,182,Carns,,6
1077,Wanted Pink Deluxe,100,Deluxe,,206,Roses Pink,,6
1077,Wanted Pink Deluxe,100,Deluxe,,180,Baby Breath,,2
1077,Wanted Pink Deluxe,100,Deluxe,,223,Bow,,1
1077,Wanted Pink Deluxe,100,Deluxe,,157,Vase Mauve,,1
1078,Sunshine of My Life Standard,115,Standard,,217,Sunflowers,,3
1078,Sunshine of My Life Standard,115,Standard,,218,Tulips,,3
1078,Sunshine of My Life Standard,115,Standard,,189,Dianthus,,4
1078,Sunshine of My Life Standard,115,Standard,,184,Cremons,,4
1078,Sunshine of My Life Standard,115,Standard,,178,Alstro,,3
1078,Sunshine of My Life Standard,115,Standard,,221,Raffia,,1
1078,Sunshine of My Life Standard,115,Standard,,162,Vase Milk Jug,,1
1079,Sunshine of My Life Deluxe,140,Deluxe,,217,Sunflowers,,3
1079,Sunshine of My Life Deluxe,140,Deluxe,,218,Tulips,,3
1079,Sunshine of My Life Deluxe,140,Deluxe,,189,Dianthus,,4
1079,Sunshine of My Life Deluxe,140,Deluxe,,184,Cremons,,4
1079,Sunshine of My Life Deluxe,140,Deluxe,,178,Alstro,,3
1079,Sunshine of My Life Deluxe,140,Deluxe,,207,Roses Red,,3
1079,Sunshine of My Life Deluxe,140,Deluxe,,221,Raffia,,1
1079,Sunshine of My Life Deluxe,140,Deluxe,,162,Vase Milk Jug,,1
1080,Sunshine of My Life Premium,175,Premium,,217,Sunflowers,,4
1080,Sunshine of My Life Premium,175,Premium,,218,Tulips,,4
1080,Sunshine of My Life Premium,175,Premium,,189,Dianthus,,5
1080,Sunshine of My Life Premium,175,Premium,,184,Cremons,,4
1080,Sunshine of My Life Premium,175,Premium,,178,Alstro,,4
1080,Sunshine of My Life Premium,175,Premium,,207,Roses Red,,5
1080,Sunshine of My Life Premium,175,Premium,,221,Raffia,,1
1080,Sunshine of My Life Premium,175,Premium,,162,Vase Milk Jug,,1
1081,You're the Bees Knees Standard,60,Standard,,210,Roses Yellow,,3
1081,You're the Bees Knees Standard,60,Standard,,,Daisies,Generic,2
1081,You're the Bees Knees Standard,60,Standard,,183,Mini Carns,,2
1081,You're the Bees Knees Standard,60,Standard,,149,Mug,,1
1082,Texas Dreamin Standard,104,Standard,,207,Roses Red,,3
1082,Texas Dreamin Standard,104,Standard,,205,Roses Lavender,,3
1082,Texas Dreamin Standard,104,Standard,,182,Carns,,3
1082,Texas Dreamin Standard,104,Standard,,182,Carns,,3
1082,Texas Dreamin Standard,104,Standard,,178,Alstro,,4
1082,Texas Dreamin Standard,104,Standard,,215,Statice,,2
1082,Texas Dreamin Standard,104,Standard,,154,Vase Bi-Color,,1
1083,Texas Dreamin Deluxe,135,Deluxe,,207,Roses Red,,5
1083,Texas Dreamin Deluxe,135,Deluxe,,205,Roses Lavender,,5
1083,Texas Dreamin Deluxe,135,Deluxe,,182,Carns,,6
1083,Texas Dreamin Deluxe,135,Deluxe,,178,Alstro,,4
1083,Texas Dreamin Deluxe,135,Deluxe,,215,Statice,,2
1083,Texas Dreamin Deluxe,135,Deluxe,,154,Vase Bi-Color,,1
1084,Disco Baby Standard,75,Standard,,,Eucalyptus,Generic,1
1084,Disco Baby Standard,75,Standard,,207,Roses Red,,3
1084,Disco Baby Standard,75,Standard,,182,Carns,,5
1084,Disco Baby Standard,75,Standard,,227,Disco Large,,1
1084,Disco Baby Standard,75,Standard,,228,Disco Small,,2
1084,Disco Baby Standard,75,Standard,,156,Vase Bubble,,1
1085,Baby Blue Eyes Standard,135,Standard,,186,Delphinium,,5
1085,Baby Blue Eyes Standard,135,Standard,,219,Veronica,,5
1085,Baby Blue Eyes Standard,135,Standard,,197,Larkspur,,2
1085,Baby Blue Eyes Standard,135,Standard,,178,Alstro,,3
1085,Baby Blue Eyes Standard,135,Standard,,182,Carns,,5
1085,Baby Blue Eyes Standard,135,Standard,,,Eucalyptus,Generic,1
1085,Baby Blue Eyes Standard,135,Standard,,155,Vase Blue,,1
1086,Baby Blue Eyes Deluxe,165,Deluxe,,186,Delphinium,,5
1086,Baby Blue Eyes Deluxe,165,Deluxe,,219,Veronica,,5
1086,Baby Blue Eyes Deluxe,165,Deluxe,,197,Larkspur,,2
1086,Baby Blue Eyes Deluxe,165,Deluxe,,178,Alstro,,3
1086,Baby Blue Eyes Deluxe,165,Deluxe,,182,Carns,,5
1086,Baby Blue Eyes Deluxe,165,Deluxe,,,Eucalyptus,Generic,1
1086,Baby Blue Eyes Deluxe,165,Deluxe,,209,Roses White,,4
1086,Baby Blue Eyes Deluxe,165,Deluxe,,155,Vase Blue,,1
"""

inventory_content = """item_id,name,category,sub_category,unit_cost,bundle_count,count_on_hand
149,Bees Knees Mug,hardgood,vase,6.0,1,0
150,Dollar Tree Glass Hurricane 6.5 inch,hardgood,vase,12.0,1,0
151,Dollar Tree Judy Vase,hardgood,vase,10.0,1,0
152,Dollar Tree Mario Vase,hardgood,vase,10.0,1,0
153,G030R Tall Red Square Vase 9.6 inch,hardgood,vase,10.0,1,0
154,King Dollar Bi-Colored (pink/blue or (smoky/maroon),hardgood,vase,10.0,1,0
155,King Dollar Blue Vase Various Styles,hardgood,vase,10.0,1,0
156,King Dollar Crystal Bubble Bowl,hardgood,vase,10.0,1,0
157,King Dollar Mauve (gathered at the top),hardgood,vase,10.0,1,0
158,King Dollar Mauve Vase (not gathered at the top),hardgood,vase,10.0,1,0
159,King Dollar Smoky Color,hardgood,vase,10.0,1,0
223,VD Bow,hardgood,bow,5.0,1,0
160,VVG1216C Murano Vase,hardgood,vase,12.0,1,0
161,VVG2079CR Red Tall Rectangle Vase,hardgood,vase,35.0,1,0
162,VVG2120C Short Milk Jug 6 inch,hardgood,vase,18.0,1,0
163,VVG2125C Tall Milk Jug 7.5 inch,hardgood,vase,16.0,1,0
164,VVG232S McGreco 7.5 inch,hardgood,vase,15.0,1,0
165,VVG2450 Austria Vase,hardgood,vase,16.0,1,0
166,VVG4049 Clear 9 inch Jordan with Ruffled-Top,hardgood,vase,15.0,1,0
167,VVG4049CP Pink Metallic Jordan,hardgood,vase,22.0,1,0
168,VVG4049CR Red metallic Jordan,hardgood,vase,22.0,1,0
169,VVG4049CS Silver Metallic Jordan,hardgood,vase,22.0,1,0
170,VVG4149 Clear Jordan 11 inch,hardgood,vase,20.0,1,0
171,VVG420 Melia Small Bulb 6 inch,hardgood,vase,15.0,1,0
172,VVG420R Melia Small Bulb Red 6 inch,hardgood,vase,20.0,1,0
173,VVG432 Large Melia,hardgood,vase,35.0,1,0
174,VVG4349 Large Diva 10 inch,hardgood,vase,20.0,1,0
175,VVG940CP 8 inch Pink Gathering Vase,hardgood,vase,20.0,1,0
176,White Ceramic Bowl 4.75 inch,hardgood,vase,15.0,1,0
227,disco ball large,hardgood,accessory,5.0,1,0
228,disco ball small,hardgood,accessory,5.0,1,0
222,wrap,hardgood,wrap,7.0,1,0
177,Achillea,stem,flower,3.0,1,0
178,Alstro,stem,flower,2.5,1,0
179,Baby blue euc,stem,flower,1.5,1,0
180,Baby's Breath,stem,filler,3.0,1,0
181,Bells of Ireland,stem,flower,4.0,1,0
182,Carnations,stem,carnation,2.0,1,0
183,Carnations: Mini carns,stem,carnation,2.0,1,0
184,Cremons,stem,mum,3.0,1,0
185,Daisies/ Cushions etc.,stem,flower,2.5,1,0
186,Delphnium - blue,stem,flower,5.0,1,0
187,Dianthus,stem,flower,3.5,1,0
188,Dianthus green ball,stem,flower,3.5,1,0
189,Dianthus reg,stem,flower,3.5,1,0
190,Eryngium,stem,flower,2.5,1,0
191,Gerbera,stem,flower,4.5,1,0
192,Ginestra,stem,flower,4.0,1,0
193,Hydrangeas - blue,stem,hydrangea,6.0,1,0
194,Hydrangeas - green,stem,hydrangea,5.0,1,0
195,Hydrangeas - white,stem,hydrangea,6.0,1,0
196,Hypericum,stem,flower,2.0,1,0
197,Larkspur,stem,flower,5.0,1,0
198,Lily LA Assorted Asiatic,stem,lily,5.0,1,0
199,Lily Stargazers,stem,lily,7.0,1,0
200,Limonium - short,stem,filler,3.0,1,0
201,Limonium - tall,stem,filler,4.0,1,0
202,Mini callas pink,stem,flower,6.0,1,0
221,Raffia,stem,flower,100.0,1,0
203,Rice Flower,stem,flower,7.0,1,0
226,Roses Aggie,stem,rose,6.0,25,0
225,Roses Bicolor,stem,rose,6.0,25,0
204,Roses Garden Roses,stem,rose,7.0,1,0
205,Roses Lavender,stem,rose,6.0,25,0
224,Roses Orange,stem,rose,6.0,25,0
206,Roses Pink,stem,rose,6.0,25,0
207,Roses Red,stem,rose,6.0,25,0
208,Roses Spray roses,stem,rose,3.0,1,0
209,Roses White,stem,rose,5.0,25,0
210,Roses Yellow,stem,rose,5.0,25,0
211,Safari Sunset,stem,flower,3.0,1,0
212,Seeded euc,stem,flower,3.0,1,0
213,Solidago,stem,filler,2.5,1,0
214,Spiders,stem,mum,3.0,1,0
215,Statice,stem,filler,2.5,1,0
216,Stock,stem,flower,4.0,1,0
217,Sunflowers,stem,flower,3.5,1,0
218,Tulips,stem,flower,4.0,1,0
219,Veronica,stem,flower,3.0,1,0
220,Wax Flower,stem,flower,3.5,1,0
"""

# Read CSVs
df_recipes = pd.read_csv(io.StringIO(recipes_content), dtype={'item_id': 'Int64'})
df_inv = pd.read_csv(io.StringIO(inventory_content))

# 1. Remove "Greenery" (Disabled: Mapping to stem instead)
# df_recipes = df_recipes[df_recipes['Ingredient'] != "Greenery"].copy()

# Create lookup map: item_id -> category
inv_map = df_inv.set_index('item_id')['category'].to_dict()

# 2. Add Category Column (initialized as empty)
df_recipes['Category'] = pd.NA

# 3. Manual Updates for Generics and Special Mappings
# Daisies -> Map to ID 185
daisy_mask = df_recipes['Ingredient'] == "Daisies"
df_recipes.loc[daisy_mask, 'item_id'] = 185
df_recipes.loc[daisy_mask, 'Category'] = 'stem'

# Eucalyptus -> Map to Generic Stem (Category 'Eucalyptus' doesn't exist)
euc_mask = df_recipes['Ingredient'] == "Eucalyptus"
df_recipes.loc[euc_mask, 'item_id'] = pd.NA
df_recipes.loc[euc_mask, 'Ingredient'] = 'Any stem'
df_recipes.loc[euc_mask, 'Category'] = 'stem'
df_recipes.loc[euc_mask, 'Note'] = 'Eucalyptus'

# Filler -> Map to Generic Stem
filler_mask = df_recipes['Ingredient'] == "Filler"
df_recipes.loc[filler_mask, 'item_id'] = pd.NA
df_recipes.loc[filler_mask, 'Ingredient'] = 'Any stem'
df_recipes.loc[filler_mask, 'Category'] = 'stem'
df_recipes.loc[filler_mask, 'Note'] = 'Filler'

# Greenery -> Map to Generic Stem
greenery_mask = df_recipes['Ingredient'] == "Greenery"
df_recipes.loc[greenery_mask, 'item_id'] = pd.NA
df_recipes.loc[greenery_mask, 'Ingredient'] = 'Any stem'
df_recipes.loc[greenery_mask, 'Category'] = 'stem'
df_recipes.loc[greenery_mask, 'Note'] = 'Greenery'

# Roses Mix -> Map to Generic Rose
roses_mix_mask = df_recipes['Ingredient'] == "Roses Mix"
df_recipes.loc[roses_mix_mask, 'item_id'] = pd.NA
df_recipes.loc[roses_mix_mask, 'Ingredient'] = 'Any rose'
df_recipes.loc[roses_mix_mask, 'Category'] = 'stem'

# 4. Map remaining items using Inventory
# We only map if Category is still NA (to preserve our manual overrides if any)
# and if item_id is present.
mask_needs_cat = df_recipes['Category'].isna() & df_recipes['item_id'].notna()
df_recipes.loc[mask_needs_cat, 'Category'] = df_recipes.loc[mask_needs_cat, 'item_id'].map(inv_map)

# 5. Format Output
# We want item_id to be an integer string if present, else empty.
# 'Int64' dtype in pandas handles this mostly, but writing to CSV might leave <NA>.
# We'll fill NA with "" for the CSV output.
df_output = df_recipes.copy()
# Convert to object to allow empty strings
df_output['item_id'] = df_output['item_id'].astype('object')
df_output['item_id'] = df_output['item_id'].fillna("")

# Print the CSV
df_output.to_csv('recipes.csv', index=False)
print("Saved to recipes.csv")