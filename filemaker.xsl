<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:fmrs="http://www.filemaker.com/xml/fmresultset"
    xmlns:fml="http://www.filemaker.com/fmpxmllayout"
    xmlns:fmq="http://www.filemaker.com/xml/query"
    xmlns:fmxslt="xalan://com.fmi.xslt.ExtensionFunctions"
    exclude-result-prefixes="xsl fmrs fmq fml fmxslt">

    <xsl:output method="xml" indent="yes" />

    <xsl:template match="//fmrs:resultset">
        <root>
            <xsl:apply-templates select="fmrs:record" />
        </root>
    </xsl:template>

    <xsl:template match="fmrs:record">
        <list-item>
            <RECORDID><xsl:value-of select="@record-id" /></RECORDID>
            <MODID><xsl:value-of select="@mod-id" /></MODID>
            <xsl:apply-templates select="fmrs:field" />
            <xsl:apply-templates select="fmrs:relatedset" />
        </list-item>
    </xsl:template>

    <xsl:template match="fmrs:field">
        <xsl:choose>
            <xsl:when test="contains(@name, '::')">
                <xsl:element name="{substring-after(@name, '::')}">
                    <xsl:value-of select="./fmrs:data" />
                </xsl:element>
            </xsl:when>
            <xsl:otherwise>
                <xsl:element name="{@name}">
                    <xsl:value-of select="./fmrs:data" />
                </xsl:element>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>

    <xsl:template match="fmrs:relatedset">
        <xsl:element name="{@table}">
            <xsl:apply-templates select="fmrs:record" />
        </xsl:element>
    </xsl:template>

</xsl:stylesheet>
