# Generated from src/parser/grammar/BSLParser.g4 by ANTLR 4.13.2
from antlr4 import *

if "." in __name__:
    from .BSLParser import BSLParser
else:
    from BSLParser import BSLParser

# This class defines a complete generic visitor for a parse tree produced by BSLParser.


class BSLParserVisitor(ParseTreeVisitor):
    # Visit a parse tree produced by BSLParser#file.
    def visitFile(self, ctx: BSLParser.FileContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#preproc_native.
    def visitPreproc_native(self, ctx: BSLParser.Preproc_nativeContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#usedLib.
    def visitUsedLib(self, ctx: BSLParser.UsedLibContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#use.
    def visitUse(self, ctx: BSLParser.UseContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#moduleAnnotations.
    def visitModuleAnnotations(self, ctx: BSLParser.ModuleAnnotationsContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#shebang.
    def visitShebang(self, ctx: BSLParser.ShebangContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#regionStart.
    def visitRegionStart(self, ctx: BSLParser.RegionStartContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#regionEnd.
    def visitRegionEnd(self, ctx: BSLParser.RegionEndContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#regionName.
    def visitRegionName(self, ctx: BSLParser.RegionNameContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#preproc_if.
    def visitPreproc_if(self, ctx: BSLParser.Preproc_ifContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#preproc_elsif.
    def visitPreproc_elsif(self, ctx: BSLParser.Preproc_elsifContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#preproc_else.
    def visitPreproc_else(self, ctx: BSLParser.Preproc_elseContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#preproc_endif.
    def visitPreproc_endif(self, ctx: BSLParser.Preproc_endifContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#preproc_expression.
    def visitPreproc_expression(self, ctx: BSLParser.Preproc_expressionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#preproc_logicalOperand.
    def visitPreproc_logicalOperand(self, ctx: BSLParser.Preproc_logicalOperandContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#preproc_logicalExpression.
    def visitPreproc_logicalExpression(
        self, ctx: BSLParser.Preproc_logicalExpressionContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#preproc_symbol.
    def visitPreproc_symbol(self, ctx: BSLParser.Preproc_symbolContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#preproc_unknownSymbol.
    def visitPreproc_unknownSymbol(self, ctx: BSLParser.Preproc_unknownSymbolContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#preproc_boolOperation.
    def visitPreproc_boolOperation(self, ctx: BSLParser.Preproc_boolOperationContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#preprocessor.
    def visitPreprocessor(self, ctx: BSLParser.PreprocessorContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#compilerDirectiveSymbol.
    def visitCompilerDirectiveSymbol(
        self, ctx: BSLParser.CompilerDirectiveSymbolContext
    ):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#compilerDirective.
    def visitCompilerDirective(self, ctx: BSLParser.CompilerDirectiveContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#annotationName.
    def visitAnnotationName(self, ctx: BSLParser.AnnotationNameContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#annotationParamName.
    def visitAnnotationParamName(self, ctx: BSLParser.AnnotationParamNameContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#annotation.
    def visitAnnotation(self, ctx: BSLParser.AnnotationContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#annotationParams.
    def visitAnnotationParams(self, ctx: BSLParser.AnnotationParamsContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#annotationParam.
    def visitAnnotationParam(self, ctx: BSLParser.AnnotationParamContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#annotationParamValue.
    def visitAnnotationParamValue(self, ctx: BSLParser.AnnotationParamValueContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#var_name.
    def visitVar_name(self, ctx: BSLParser.Var_nameContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#moduleVars.
    def visitModuleVars(self, ctx: BSLParser.ModuleVarsContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#moduleVar.
    def visitModuleVar(self, ctx: BSLParser.ModuleVarContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#moduleVarsList.
    def visitModuleVarsList(self, ctx: BSLParser.ModuleVarsListContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#moduleVarDeclaration.
    def visitModuleVarDeclaration(self, ctx: BSLParser.ModuleVarDeclarationContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#subVars.
    def visitSubVars(self, ctx: BSLParser.SubVarsContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#subVar.
    def visitSubVar(self, ctx: BSLParser.SubVarContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#subVarsList.
    def visitSubVarsList(self, ctx: BSLParser.SubVarsListContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#subVarDeclaration.
    def visitSubVarDeclaration(self, ctx: BSLParser.SubVarDeclarationContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#subName.
    def visitSubName(self, ctx: BSLParser.SubNameContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#subs.
    def visitSubs(self, ctx: BSLParser.SubsContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#sub.
    def visitSub(self, ctx: BSLParser.SubContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#procedure.
    def visitProcedure(self, ctx: BSLParser.ProcedureContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#function.
    def visitFunction(self, ctx: BSLParser.FunctionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#procDeclaration.
    def visitProcDeclaration(self, ctx: BSLParser.ProcDeclarationContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#funcDeclaration.
    def visitFuncDeclaration(self, ctx: BSLParser.FuncDeclarationContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#subCodeBlock.
    def visitSubCodeBlock(self, ctx: BSLParser.SubCodeBlockContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#continueStatement.
    def visitContinueStatement(self, ctx: BSLParser.ContinueStatementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#breakStatement.
    def visitBreakStatement(self, ctx: BSLParser.BreakStatementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#raiseStatement.
    def visitRaiseStatement(self, ctx: BSLParser.RaiseStatementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#ifStatement.
    def visitIfStatement(self, ctx: BSLParser.IfStatementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#ifBranch.
    def visitIfBranch(self, ctx: BSLParser.IfBranchContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#elsifBranch.
    def visitElsifBranch(self, ctx: BSLParser.ElsifBranchContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#elseBranch.
    def visitElseBranch(self, ctx: BSLParser.ElseBranchContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#whileStatement.
    def visitWhileStatement(self, ctx: BSLParser.WhileStatementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#forStatement.
    def visitForStatement(self, ctx: BSLParser.ForStatementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#forEachStatement.
    def visitForEachStatement(self, ctx: BSLParser.ForEachStatementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#tryStatement.
    def visitTryStatement(self, ctx: BSLParser.TryStatementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#returnStatement.
    def visitReturnStatement(self, ctx: BSLParser.ReturnStatementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#executeStatement.
    def visitExecuteStatement(self, ctx: BSLParser.ExecuteStatementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#callStatement.
    def visitCallStatement(self, ctx: BSLParser.CallStatementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#waitStatement.
    def visitWaitStatement(self, ctx: BSLParser.WaitStatementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#labelName.
    def visitLabelName(self, ctx: BSLParser.LabelNameContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#label.
    def visitLabel(self, ctx: BSLParser.LabelContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#gotoStatement.
    def visitGotoStatement(self, ctx: BSLParser.GotoStatementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#tryCodeBlock.
    def visitTryCodeBlock(self, ctx: BSLParser.TryCodeBlockContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#exceptCodeBlock.
    def visitExceptCodeBlock(self, ctx: BSLParser.ExceptCodeBlockContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#event.
    def visitEvent(self, ctx: BSLParser.EventContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#handler.
    def visitHandler(self, ctx: BSLParser.HandlerContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#addHandlerStatement.
    def visitAddHandlerStatement(self, ctx: BSLParser.AddHandlerStatementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#removeHandlerStatement.
    def visitRemoveHandlerStatement(self, ctx: BSLParser.RemoveHandlerStatementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#ternaryOperator.
    def visitTernaryOperator(self, ctx: BSLParser.TernaryOperatorContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#waitExpression.
    def visitWaitExpression(self, ctx: BSLParser.WaitExpressionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#fileCodeBlockBeforeSub.
    def visitFileCodeBlockBeforeSub(self, ctx: BSLParser.FileCodeBlockBeforeSubContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#fileCodeBlock.
    def visitFileCodeBlock(self, ctx: BSLParser.FileCodeBlockContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#codeBlock.
    def visitCodeBlock(self, ctx: BSLParser.CodeBlockContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#numeric.
    def visitNumeric(self, ctx: BSLParser.NumericContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#paramList.
    def visitParamList(self, ctx: BSLParser.ParamListContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#param.
    def visitParam(self, ctx: BSLParser.ParamContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#defaultValue.
    def visitDefaultValue(self, ctx: BSLParser.DefaultValueContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#constValue.
    def visitConstValue(self, ctx: BSLParser.ConstValueContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#multilineString.
    def visitMultilineString(self, ctx: BSLParser.MultilineStringContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#string.
    def visitString(self, ctx: BSLParser.StringContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#statement.
    def visitStatement(self, ctx: BSLParser.StatementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#assignment.
    def visitAssignment(self, ctx: BSLParser.AssignmentContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#callParamList.
    def visitCallParamList(self, ctx: BSLParser.CallParamListContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#callParam.
    def visitCallParam(self, ctx: BSLParser.CallParamContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#expression.
    def visitExpression(self, ctx: BSLParser.ExpressionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#operation.
    def visitOperation(self, ctx: BSLParser.OperationContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#compareOperation.
    def visitCompareOperation(self, ctx: BSLParser.CompareOperationContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#boolOperation.
    def visitBoolOperation(self, ctx: BSLParser.BoolOperationContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#unaryModifier.
    def visitUnaryModifier(self, ctx: BSLParser.UnaryModifierContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#member.
    def visitMember(self, ctx: BSLParser.MemberContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#newExpression.
    def visitNewExpression(self, ctx: BSLParser.NewExpressionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#typeName.
    def visitTypeName(self, ctx: BSLParser.TypeNameContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#methodCall.
    def visitMethodCall(self, ctx: BSLParser.MethodCallContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#globalMethodCall.
    def visitGlobalMethodCall(self, ctx: BSLParser.GlobalMethodCallContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#methodName.
    def visitMethodName(self, ctx: BSLParser.MethodNameContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#complexIdentifier.
    def visitComplexIdentifier(self, ctx: BSLParser.ComplexIdentifierContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#modifier.
    def visitModifier(self, ctx: BSLParser.ModifierContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#acceptor.
    def visitAcceptor(self, ctx: BSLParser.AcceptorContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#lValue.
    def visitLValue(self, ctx: BSLParser.LValueContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#accessCall.
    def visitAccessCall(self, ctx: BSLParser.AccessCallContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#accessIndex.
    def visitAccessIndex(self, ctx: BSLParser.AccessIndexContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#accessProperty.
    def visitAccessProperty(self, ctx: BSLParser.AccessPropertyContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#doCall.
    def visitDoCall(self, ctx: BSLParser.DoCallContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by BSLParser#compoundStatement.
    def visitCompoundStatement(self, ctx: BSLParser.CompoundStatementContext):
        return self.visitChildren(ctx)


del BSLParser
