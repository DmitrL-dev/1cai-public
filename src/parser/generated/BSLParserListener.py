# Generated from src/parser/grammar/BSLParser.g4 by ANTLR 4.13.2
from antlr4 import *

if "." in __name__:
    from .BSLParser import BSLParser
else:
    from BSLParser import BSLParser


# This class defines a complete listener for a parse tree produced by BSLParser.
class BSLParserListener(ParseTreeListener):
    # Enter a parse tree produced by BSLParser#file.
    def enterFile(self, ctx: BSLParser.FileContext):
        pass

    # Exit a parse tree produced by BSLParser#file.
    def exitFile(self, ctx: BSLParser.FileContext):
        pass

    # Enter a parse tree produced by BSLParser#preproc_native.
    def enterPreproc_native(self, ctx: BSLParser.Preproc_nativeContext):
        pass

    # Exit a parse tree produced by BSLParser#preproc_native.
    def exitPreproc_native(self, ctx: BSLParser.Preproc_nativeContext):
        pass

    # Enter a parse tree produced by BSLParser#usedLib.
    def enterUsedLib(self, ctx: BSLParser.UsedLibContext):
        pass

    # Exit a parse tree produced by BSLParser#usedLib.
    def exitUsedLib(self, ctx: BSLParser.UsedLibContext):
        pass

    # Enter a parse tree produced by BSLParser#use.
    def enterUse(self, ctx: BSLParser.UseContext):
        pass

    # Exit a parse tree produced by BSLParser#use.
    def exitUse(self, ctx: BSLParser.UseContext):
        pass

    # Enter a parse tree produced by BSLParser#moduleAnnotations.
    def enterModuleAnnotations(self, ctx: BSLParser.ModuleAnnotationsContext):
        pass

    # Exit a parse tree produced by BSLParser#moduleAnnotations.
    def exitModuleAnnotations(self, ctx: BSLParser.ModuleAnnotationsContext):
        pass

    # Enter a parse tree produced by BSLParser#shebang.
    def enterShebang(self, ctx: BSLParser.ShebangContext):
        pass

    # Exit a parse tree produced by BSLParser#shebang.
    def exitShebang(self, ctx: BSLParser.ShebangContext):
        pass

    # Enter a parse tree produced by BSLParser#regionStart.
    def enterRegionStart(self, ctx: BSLParser.RegionStartContext):
        pass

    # Exit a parse tree produced by BSLParser#regionStart.
    def exitRegionStart(self, ctx: BSLParser.RegionStartContext):
        pass

    # Enter a parse tree produced by BSLParser#regionEnd.
    def enterRegionEnd(self, ctx: BSLParser.RegionEndContext):
        pass

    # Exit a parse tree produced by BSLParser#regionEnd.
    def exitRegionEnd(self, ctx: BSLParser.RegionEndContext):
        pass

    # Enter a parse tree produced by BSLParser#regionName.
    def enterRegionName(self, ctx: BSLParser.RegionNameContext):
        pass

    # Exit a parse tree produced by BSLParser#regionName.
    def exitRegionName(self, ctx: BSLParser.RegionNameContext):
        pass

    # Enter a parse tree produced by BSLParser#preproc_if.
    def enterPreproc_if(self, ctx: BSLParser.Preproc_ifContext):
        pass

    # Exit a parse tree produced by BSLParser#preproc_if.
    def exitPreproc_if(self, ctx: BSLParser.Preproc_ifContext):
        pass

    # Enter a parse tree produced by BSLParser#preproc_elsif.
    def enterPreproc_elsif(self, ctx: BSLParser.Preproc_elsifContext):
        pass

    # Exit a parse tree produced by BSLParser#preproc_elsif.
    def exitPreproc_elsif(self, ctx: BSLParser.Preproc_elsifContext):
        pass

    # Enter a parse tree produced by BSLParser#preproc_else.
    def enterPreproc_else(self, ctx: BSLParser.Preproc_elseContext):
        pass

    # Exit a parse tree produced by BSLParser#preproc_else.
    def exitPreproc_else(self, ctx: BSLParser.Preproc_elseContext):
        pass

    # Enter a parse tree produced by BSLParser#preproc_endif.
    def enterPreproc_endif(self, ctx: BSLParser.Preproc_endifContext):
        pass

    # Exit a parse tree produced by BSLParser#preproc_endif.
    def exitPreproc_endif(self, ctx: BSLParser.Preproc_endifContext):
        pass

    # Enter a parse tree produced by BSLParser#preproc_expression.
    def enterPreproc_expression(self, ctx: BSLParser.Preproc_expressionContext):
        pass

    # Exit a parse tree produced by BSLParser#preproc_expression.
    def exitPreproc_expression(self, ctx: BSLParser.Preproc_expressionContext):
        pass

    # Enter a parse tree produced by BSLParser#preproc_logicalOperand.
    def enterPreproc_logicalOperand(self, ctx: BSLParser.Preproc_logicalOperandContext):
        pass

    # Exit a parse tree produced by BSLParser#preproc_logicalOperand.
    def exitPreproc_logicalOperand(self, ctx: BSLParser.Preproc_logicalOperandContext):
        pass

    # Enter a parse tree produced by BSLParser#preproc_logicalExpression.
    def enterPreproc_logicalExpression(
        self, ctx: BSLParser.Preproc_logicalExpressionContext
    ):
        pass

    # Exit a parse tree produced by BSLParser#preproc_logicalExpression.
    def exitPreproc_logicalExpression(
        self, ctx: BSLParser.Preproc_logicalExpressionContext
    ):
        pass

    # Enter a parse tree produced by BSLParser#preproc_symbol.
    def enterPreproc_symbol(self, ctx: BSLParser.Preproc_symbolContext):
        pass

    # Exit a parse tree produced by BSLParser#preproc_symbol.
    def exitPreproc_symbol(self, ctx: BSLParser.Preproc_symbolContext):
        pass

    # Enter a parse tree produced by BSLParser#preproc_unknownSymbol.
    def enterPreproc_unknownSymbol(self, ctx: BSLParser.Preproc_unknownSymbolContext):
        pass

    # Exit a parse tree produced by BSLParser#preproc_unknownSymbol.
    def exitPreproc_unknownSymbol(self, ctx: BSLParser.Preproc_unknownSymbolContext):
        pass

    # Enter a parse tree produced by BSLParser#preproc_boolOperation.
    def enterPreproc_boolOperation(self, ctx: BSLParser.Preproc_boolOperationContext):
        pass

    # Exit a parse tree produced by BSLParser#preproc_boolOperation.
    def exitPreproc_boolOperation(self, ctx: BSLParser.Preproc_boolOperationContext):
        pass

    # Enter a parse tree produced by BSLParser#preprocessor.
    def enterPreprocessor(self, ctx: BSLParser.PreprocessorContext):
        pass

    # Exit a parse tree produced by BSLParser#preprocessor.
    def exitPreprocessor(self, ctx: BSLParser.PreprocessorContext):
        pass

    # Enter a parse tree produced by BSLParser#compilerDirectiveSymbol.
    def enterCompilerDirectiveSymbol(
        self, ctx: BSLParser.CompilerDirectiveSymbolContext
    ):
        pass

    # Exit a parse tree produced by BSLParser#compilerDirectiveSymbol.
    def exitCompilerDirectiveSymbol(
        self, ctx: BSLParser.CompilerDirectiveSymbolContext
    ):
        pass

    # Enter a parse tree produced by BSLParser#compilerDirective.
    def enterCompilerDirective(self, ctx: BSLParser.CompilerDirectiveContext):
        pass

    # Exit a parse tree produced by BSLParser#compilerDirective.
    def exitCompilerDirective(self, ctx: BSLParser.CompilerDirectiveContext):
        pass

    # Enter a parse tree produced by BSLParser#annotationName.
    def enterAnnotationName(self, ctx: BSLParser.AnnotationNameContext):
        pass

    # Exit a parse tree produced by BSLParser#annotationName.
    def exitAnnotationName(self, ctx: BSLParser.AnnotationNameContext):
        pass

    # Enter a parse tree produced by BSLParser#annotationParamName.
    def enterAnnotationParamName(self, ctx: BSLParser.AnnotationParamNameContext):
        pass

    # Exit a parse tree produced by BSLParser#annotationParamName.
    def exitAnnotationParamName(self, ctx: BSLParser.AnnotationParamNameContext):
        pass

    # Enter a parse tree produced by BSLParser#annotation.
    def enterAnnotation(self, ctx: BSLParser.AnnotationContext):
        pass

    # Exit a parse tree produced by BSLParser#annotation.
    def exitAnnotation(self, ctx: BSLParser.AnnotationContext):
        pass

    # Enter a parse tree produced by BSLParser#annotationParams.
    def enterAnnotationParams(self, ctx: BSLParser.AnnotationParamsContext):
        pass

    # Exit a parse tree produced by BSLParser#annotationParams.
    def exitAnnotationParams(self, ctx: BSLParser.AnnotationParamsContext):
        pass

    # Enter a parse tree produced by BSLParser#annotationParam.
    def enterAnnotationParam(self, ctx: BSLParser.AnnotationParamContext):
        pass

    # Exit a parse tree produced by BSLParser#annotationParam.
    def exitAnnotationParam(self, ctx: BSLParser.AnnotationParamContext):
        pass

    # Enter a parse tree produced by BSLParser#annotationParamValue.
    def enterAnnotationParamValue(self, ctx: BSLParser.AnnotationParamValueContext):
        pass

    # Exit a parse tree produced by BSLParser#annotationParamValue.
    def exitAnnotationParamValue(self, ctx: BSLParser.AnnotationParamValueContext):
        pass

    # Enter a parse tree produced by BSLParser#var_name.
    def enterVar_name(self, ctx: BSLParser.Var_nameContext):
        pass

    # Exit a parse tree produced by BSLParser#var_name.
    def exitVar_name(self, ctx: BSLParser.Var_nameContext):
        pass

    # Enter a parse tree produced by BSLParser#moduleVars.
    def enterModuleVars(self, ctx: BSLParser.ModuleVarsContext):
        pass

    # Exit a parse tree produced by BSLParser#moduleVars.
    def exitModuleVars(self, ctx: BSLParser.ModuleVarsContext):
        pass

    # Enter a parse tree produced by BSLParser#moduleVar.
    def enterModuleVar(self, ctx: BSLParser.ModuleVarContext):
        pass

    # Exit a parse tree produced by BSLParser#moduleVar.
    def exitModuleVar(self, ctx: BSLParser.ModuleVarContext):
        pass

    # Enter a parse tree produced by BSLParser#moduleVarsList.
    def enterModuleVarsList(self, ctx: BSLParser.ModuleVarsListContext):
        pass

    # Exit a parse tree produced by BSLParser#moduleVarsList.
    def exitModuleVarsList(self, ctx: BSLParser.ModuleVarsListContext):
        pass

    # Enter a parse tree produced by BSLParser#moduleVarDeclaration.
    def enterModuleVarDeclaration(self, ctx: BSLParser.ModuleVarDeclarationContext):
        pass

    # Exit a parse tree produced by BSLParser#moduleVarDeclaration.
    def exitModuleVarDeclaration(self, ctx: BSLParser.ModuleVarDeclarationContext):
        pass

    # Enter a parse tree produced by BSLParser#subVars.
    def enterSubVars(self, ctx: BSLParser.SubVarsContext):
        pass

    # Exit a parse tree produced by BSLParser#subVars.
    def exitSubVars(self, ctx: BSLParser.SubVarsContext):
        pass

    # Enter a parse tree produced by BSLParser#subVar.
    def enterSubVar(self, ctx: BSLParser.SubVarContext):
        pass

    # Exit a parse tree produced by BSLParser#subVar.
    def exitSubVar(self, ctx: BSLParser.SubVarContext):
        pass

    # Enter a parse tree produced by BSLParser#subVarsList.
    def enterSubVarsList(self, ctx: BSLParser.SubVarsListContext):
        pass

    # Exit a parse tree produced by BSLParser#subVarsList.
    def exitSubVarsList(self, ctx: BSLParser.SubVarsListContext):
        pass

    # Enter a parse tree produced by BSLParser#subVarDeclaration.
    def enterSubVarDeclaration(self, ctx: BSLParser.SubVarDeclarationContext):
        pass

    # Exit a parse tree produced by BSLParser#subVarDeclaration.
    def exitSubVarDeclaration(self, ctx: BSLParser.SubVarDeclarationContext):
        pass

    # Enter a parse tree produced by BSLParser#subName.
    def enterSubName(self, ctx: BSLParser.SubNameContext):
        pass

    # Exit a parse tree produced by BSLParser#subName.
    def exitSubName(self, ctx: BSLParser.SubNameContext):
        pass

    # Enter a parse tree produced by BSLParser#subs.
    def enterSubs(self, ctx: BSLParser.SubsContext):
        pass

    # Exit a parse tree produced by BSLParser#subs.
    def exitSubs(self, ctx: BSLParser.SubsContext):
        pass

    # Enter a parse tree produced by BSLParser#sub.
    def enterSub(self, ctx: BSLParser.SubContext):
        pass

    # Exit a parse tree produced by BSLParser#sub.
    def exitSub(self, ctx: BSLParser.SubContext):
        pass

    # Enter a parse tree produced by BSLParser#procedure.
    def enterProcedure(self, ctx: BSLParser.ProcedureContext):
        pass

    # Exit a parse tree produced by BSLParser#procedure.
    def exitProcedure(self, ctx: BSLParser.ProcedureContext):
        pass

    # Enter a parse tree produced by BSLParser#function.
    def enterFunction(self, ctx: BSLParser.FunctionContext):
        pass

    # Exit a parse tree produced by BSLParser#function.
    def exitFunction(self, ctx: BSLParser.FunctionContext):
        pass

    # Enter a parse tree produced by BSLParser#procDeclaration.
    def enterProcDeclaration(self, ctx: BSLParser.ProcDeclarationContext):
        pass

    # Exit a parse tree produced by BSLParser#procDeclaration.
    def exitProcDeclaration(self, ctx: BSLParser.ProcDeclarationContext):
        pass

    # Enter a parse tree produced by BSLParser#funcDeclaration.
    def enterFuncDeclaration(self, ctx: BSLParser.FuncDeclarationContext):
        pass

    # Exit a parse tree produced by BSLParser#funcDeclaration.
    def exitFuncDeclaration(self, ctx: BSLParser.FuncDeclarationContext):
        pass

    # Enter a parse tree produced by BSLParser#subCodeBlock.
    def enterSubCodeBlock(self, ctx: BSLParser.SubCodeBlockContext):
        pass

    # Exit a parse tree produced by BSLParser#subCodeBlock.
    def exitSubCodeBlock(self, ctx: BSLParser.SubCodeBlockContext):
        pass

    # Enter a parse tree produced by BSLParser#continueStatement.
    def enterContinueStatement(self, ctx: BSLParser.ContinueStatementContext):
        pass

    # Exit a parse tree produced by BSLParser#continueStatement.
    def exitContinueStatement(self, ctx: BSLParser.ContinueStatementContext):
        pass

    # Enter a parse tree produced by BSLParser#breakStatement.
    def enterBreakStatement(self, ctx: BSLParser.BreakStatementContext):
        pass

    # Exit a parse tree produced by BSLParser#breakStatement.
    def exitBreakStatement(self, ctx: BSLParser.BreakStatementContext):
        pass

    # Enter a parse tree produced by BSLParser#raiseStatement.
    def enterRaiseStatement(self, ctx: BSLParser.RaiseStatementContext):
        pass

    # Exit a parse tree produced by BSLParser#raiseStatement.
    def exitRaiseStatement(self, ctx: BSLParser.RaiseStatementContext):
        pass

    # Enter a parse tree produced by BSLParser#ifStatement.
    def enterIfStatement(self, ctx: BSLParser.IfStatementContext):
        pass

    # Exit a parse tree produced by BSLParser#ifStatement.
    def exitIfStatement(self, ctx: BSLParser.IfStatementContext):
        pass

    # Enter a parse tree produced by BSLParser#ifBranch.
    def enterIfBranch(self, ctx: BSLParser.IfBranchContext):
        pass

    # Exit a parse tree produced by BSLParser#ifBranch.
    def exitIfBranch(self, ctx: BSLParser.IfBranchContext):
        pass

    # Enter a parse tree produced by BSLParser#elsifBranch.
    def enterElsifBranch(self, ctx: BSLParser.ElsifBranchContext):
        pass

    # Exit a parse tree produced by BSLParser#elsifBranch.
    def exitElsifBranch(self, ctx: BSLParser.ElsifBranchContext):
        pass

    # Enter a parse tree produced by BSLParser#elseBranch.
    def enterElseBranch(self, ctx: BSLParser.ElseBranchContext):
        pass

    # Exit a parse tree produced by BSLParser#elseBranch.
    def exitElseBranch(self, ctx: BSLParser.ElseBranchContext):
        pass

    # Enter a parse tree produced by BSLParser#whileStatement.
    def enterWhileStatement(self, ctx: BSLParser.WhileStatementContext):
        pass

    # Exit a parse tree produced by BSLParser#whileStatement.
    def exitWhileStatement(self, ctx: BSLParser.WhileStatementContext):
        pass

    # Enter a parse tree produced by BSLParser#forStatement.
    def enterForStatement(self, ctx: BSLParser.ForStatementContext):
        pass

    # Exit a parse tree produced by BSLParser#forStatement.
    def exitForStatement(self, ctx: BSLParser.ForStatementContext):
        pass

    # Enter a parse tree produced by BSLParser#forEachStatement.
    def enterForEachStatement(self, ctx: BSLParser.ForEachStatementContext):
        pass

    # Exit a parse tree produced by BSLParser#forEachStatement.
    def exitForEachStatement(self, ctx: BSLParser.ForEachStatementContext):
        pass

    # Enter a parse tree produced by BSLParser#tryStatement.
    def enterTryStatement(self, ctx: BSLParser.TryStatementContext):
        pass

    # Exit a parse tree produced by BSLParser#tryStatement.
    def exitTryStatement(self, ctx: BSLParser.TryStatementContext):
        pass

    # Enter a parse tree produced by BSLParser#returnStatement.
    def enterReturnStatement(self, ctx: BSLParser.ReturnStatementContext):
        pass

    # Exit a parse tree produced by BSLParser#returnStatement.
    def exitReturnStatement(self, ctx: BSLParser.ReturnStatementContext):
        pass

    # Enter a parse tree produced by BSLParser#executeStatement.
    def enterExecuteStatement(self, ctx: BSLParser.ExecuteStatementContext):
        pass

    # Exit a parse tree produced by BSLParser#executeStatement.
    def exitExecuteStatement(self, ctx: BSLParser.ExecuteStatementContext):
        pass

    # Enter a parse tree produced by BSLParser#callStatement.
    def enterCallStatement(self, ctx: BSLParser.CallStatementContext):
        pass

    # Exit a parse tree produced by BSLParser#callStatement.
    def exitCallStatement(self, ctx: BSLParser.CallStatementContext):
        pass

    # Enter a parse tree produced by BSLParser#waitStatement.
    def enterWaitStatement(self, ctx: BSLParser.WaitStatementContext):
        pass

    # Exit a parse tree produced by BSLParser#waitStatement.
    def exitWaitStatement(self, ctx: BSLParser.WaitStatementContext):
        pass

    # Enter a parse tree produced by BSLParser#labelName.
    def enterLabelName(self, ctx: BSLParser.LabelNameContext):
        pass

    # Exit a parse tree produced by BSLParser#labelName.
    def exitLabelName(self, ctx: BSLParser.LabelNameContext):
        pass

    # Enter a parse tree produced by BSLParser#label.
    def enterLabel(self, ctx: BSLParser.LabelContext):
        pass

    # Exit a parse tree produced by BSLParser#label.
    def exitLabel(self, ctx: BSLParser.LabelContext):
        pass

    # Enter a parse tree produced by BSLParser#gotoStatement.
    def enterGotoStatement(self, ctx: BSLParser.GotoStatementContext):
        pass

    # Exit a parse tree produced by BSLParser#gotoStatement.
    def exitGotoStatement(self, ctx: BSLParser.GotoStatementContext):
        pass

    # Enter a parse tree produced by BSLParser#tryCodeBlock.
    def enterTryCodeBlock(self, ctx: BSLParser.TryCodeBlockContext):
        pass

    # Exit a parse tree produced by BSLParser#tryCodeBlock.
    def exitTryCodeBlock(self, ctx: BSLParser.TryCodeBlockContext):
        pass

    # Enter a parse tree produced by BSLParser#exceptCodeBlock.
    def enterExceptCodeBlock(self, ctx: BSLParser.ExceptCodeBlockContext):
        pass

    # Exit a parse tree produced by BSLParser#exceptCodeBlock.
    def exitExceptCodeBlock(self, ctx: BSLParser.ExceptCodeBlockContext):
        pass

    # Enter a parse tree produced by BSLParser#event.
    def enterEvent(self, ctx: BSLParser.EventContext):
        pass

    # Exit a parse tree produced by BSLParser#event.
    def exitEvent(self, ctx: BSLParser.EventContext):
        pass

    # Enter a parse tree produced by BSLParser#handler.
    def enterHandler(self, ctx: BSLParser.HandlerContext):
        pass

    # Exit a parse tree produced by BSLParser#handler.
    def exitHandler(self, ctx: BSLParser.HandlerContext):
        pass

    # Enter a parse tree produced by BSLParser#addHandlerStatement.
    def enterAddHandlerStatement(self, ctx: BSLParser.AddHandlerStatementContext):
        pass

    # Exit a parse tree produced by BSLParser#addHandlerStatement.
    def exitAddHandlerStatement(self, ctx: BSLParser.AddHandlerStatementContext):
        pass

    # Enter a parse tree produced by BSLParser#removeHandlerStatement.
    def enterRemoveHandlerStatement(self, ctx: BSLParser.RemoveHandlerStatementContext):
        pass

    # Exit a parse tree produced by BSLParser#removeHandlerStatement.
    def exitRemoveHandlerStatement(self, ctx: BSLParser.RemoveHandlerStatementContext):
        pass

    # Enter a parse tree produced by BSLParser#ternaryOperator.
    def enterTernaryOperator(self, ctx: BSLParser.TernaryOperatorContext):
        pass

    # Exit a parse tree produced by BSLParser#ternaryOperator.
    def exitTernaryOperator(self, ctx: BSLParser.TernaryOperatorContext):
        pass

    # Enter a parse tree produced by BSLParser#waitExpression.
    def enterWaitExpression(self, ctx: BSLParser.WaitExpressionContext):
        pass

    # Exit a parse tree produced by BSLParser#waitExpression.
    def exitWaitExpression(self, ctx: BSLParser.WaitExpressionContext):
        pass

    # Enter a parse tree produced by BSLParser#fileCodeBlockBeforeSub.
    def enterFileCodeBlockBeforeSub(self, ctx: BSLParser.FileCodeBlockBeforeSubContext):
        pass

    # Exit a parse tree produced by BSLParser#fileCodeBlockBeforeSub.
    def exitFileCodeBlockBeforeSub(self, ctx: BSLParser.FileCodeBlockBeforeSubContext):
        pass

    # Enter a parse tree produced by BSLParser#fileCodeBlock.
    def enterFileCodeBlock(self, ctx: BSLParser.FileCodeBlockContext):
        pass

    # Exit a parse tree produced by BSLParser#fileCodeBlock.
    def exitFileCodeBlock(self, ctx: BSLParser.FileCodeBlockContext):
        pass

    # Enter a parse tree produced by BSLParser#codeBlock.
    def enterCodeBlock(self, ctx: BSLParser.CodeBlockContext):
        pass

    # Exit a parse tree produced by BSLParser#codeBlock.
    def exitCodeBlock(self, ctx: BSLParser.CodeBlockContext):
        pass

    # Enter a parse tree produced by BSLParser#numeric.
    def enterNumeric(self, ctx: BSLParser.NumericContext):
        pass

    # Exit a parse tree produced by BSLParser#numeric.
    def exitNumeric(self, ctx: BSLParser.NumericContext):
        pass

    # Enter a parse tree produced by BSLParser#paramList.
    def enterParamList(self, ctx: BSLParser.ParamListContext):
        pass

    # Exit a parse tree produced by BSLParser#paramList.
    def exitParamList(self, ctx: BSLParser.ParamListContext):
        pass

    # Enter a parse tree produced by BSLParser#param.
    def enterParam(self, ctx: BSLParser.ParamContext):
        pass

    # Exit a parse tree produced by BSLParser#param.
    def exitParam(self, ctx: BSLParser.ParamContext):
        pass

    # Enter a parse tree produced by BSLParser#defaultValue.
    def enterDefaultValue(self, ctx: BSLParser.DefaultValueContext):
        pass

    # Exit a parse tree produced by BSLParser#defaultValue.
    def exitDefaultValue(self, ctx: BSLParser.DefaultValueContext):
        pass

    # Enter a parse tree produced by BSLParser#constValue.
    def enterConstValue(self, ctx: BSLParser.ConstValueContext):
        pass

    # Exit a parse tree produced by BSLParser#constValue.
    def exitConstValue(self, ctx: BSLParser.ConstValueContext):
        pass

    # Enter a parse tree produced by BSLParser#multilineString.
    def enterMultilineString(self, ctx: BSLParser.MultilineStringContext):
        pass

    # Exit a parse tree produced by BSLParser#multilineString.
    def exitMultilineString(self, ctx: BSLParser.MultilineStringContext):
        pass

    # Enter a parse tree produced by BSLParser#string.
    def enterString(self, ctx: BSLParser.StringContext):
        pass

    # Exit a parse tree produced by BSLParser#string.
    def exitString(self, ctx: BSLParser.StringContext):
        pass

    # Enter a parse tree produced by BSLParser#statement.
    def enterStatement(self, ctx: BSLParser.StatementContext):
        pass

    # Exit a parse tree produced by BSLParser#statement.
    def exitStatement(self, ctx: BSLParser.StatementContext):
        pass

    # Enter a parse tree produced by BSLParser#assignment.
    def enterAssignment(self, ctx: BSLParser.AssignmentContext):
        pass

    # Exit a parse tree produced by BSLParser#assignment.
    def exitAssignment(self, ctx: BSLParser.AssignmentContext):
        pass

    # Enter a parse tree produced by BSLParser#callParamList.
    def enterCallParamList(self, ctx: BSLParser.CallParamListContext):
        pass

    # Exit a parse tree produced by BSLParser#callParamList.
    def exitCallParamList(self, ctx: BSLParser.CallParamListContext):
        pass

    # Enter a parse tree produced by BSLParser#callParam.
    def enterCallParam(self, ctx: BSLParser.CallParamContext):
        pass

    # Exit a parse tree produced by BSLParser#callParam.
    def exitCallParam(self, ctx: BSLParser.CallParamContext):
        pass

    # Enter a parse tree produced by BSLParser#expression.
    def enterExpression(self, ctx: BSLParser.ExpressionContext):
        pass

    # Exit a parse tree produced by BSLParser#expression.
    def exitExpression(self, ctx: BSLParser.ExpressionContext):
        pass

    # Enter a parse tree produced by BSLParser#operation.
    def enterOperation(self, ctx: BSLParser.OperationContext):
        pass

    # Exit a parse tree produced by BSLParser#operation.
    def exitOperation(self, ctx: BSLParser.OperationContext):
        pass

    # Enter a parse tree produced by BSLParser#compareOperation.
    def enterCompareOperation(self, ctx: BSLParser.CompareOperationContext):
        pass

    # Exit a parse tree produced by BSLParser#compareOperation.
    def exitCompareOperation(self, ctx: BSLParser.CompareOperationContext):
        pass

    # Enter a parse tree produced by BSLParser#boolOperation.
    def enterBoolOperation(self, ctx: BSLParser.BoolOperationContext):
        pass

    # Exit a parse tree produced by BSLParser#boolOperation.
    def exitBoolOperation(self, ctx: BSLParser.BoolOperationContext):
        pass

    # Enter a parse tree produced by BSLParser#unaryModifier.
    def enterUnaryModifier(self, ctx: BSLParser.UnaryModifierContext):
        pass

    # Exit a parse tree produced by BSLParser#unaryModifier.
    def exitUnaryModifier(self, ctx: BSLParser.UnaryModifierContext):
        pass

    # Enter a parse tree produced by BSLParser#member.
    def enterMember(self, ctx: BSLParser.MemberContext):
        pass

    # Exit a parse tree produced by BSLParser#member.
    def exitMember(self, ctx: BSLParser.MemberContext):
        pass

    # Enter a parse tree produced by BSLParser#newExpression.
    def enterNewExpression(self, ctx: BSLParser.NewExpressionContext):
        pass

    # Exit a parse tree produced by BSLParser#newExpression.
    def exitNewExpression(self, ctx: BSLParser.NewExpressionContext):
        pass

    # Enter a parse tree produced by BSLParser#typeName.
    def enterTypeName(self, ctx: BSLParser.TypeNameContext):
        pass

    # Exit a parse tree produced by BSLParser#typeName.
    def exitTypeName(self, ctx: BSLParser.TypeNameContext):
        pass

    # Enter a parse tree produced by BSLParser#methodCall.
    def enterMethodCall(self, ctx: BSLParser.MethodCallContext):
        pass

    # Exit a parse tree produced by BSLParser#methodCall.
    def exitMethodCall(self, ctx: BSLParser.MethodCallContext):
        pass

    # Enter a parse tree produced by BSLParser#globalMethodCall.
    def enterGlobalMethodCall(self, ctx: BSLParser.GlobalMethodCallContext):
        pass

    # Exit a parse tree produced by BSLParser#globalMethodCall.
    def exitGlobalMethodCall(self, ctx: BSLParser.GlobalMethodCallContext):
        pass

    # Enter a parse tree produced by BSLParser#methodName.
    def enterMethodName(self, ctx: BSLParser.MethodNameContext):
        pass

    # Exit a parse tree produced by BSLParser#methodName.
    def exitMethodName(self, ctx: BSLParser.MethodNameContext):
        pass

    # Enter a parse tree produced by BSLParser#complexIdentifier.
    def enterComplexIdentifier(self, ctx: BSLParser.ComplexIdentifierContext):
        pass

    # Exit a parse tree produced by BSLParser#complexIdentifier.
    def exitComplexIdentifier(self, ctx: BSLParser.ComplexIdentifierContext):
        pass

    # Enter a parse tree produced by BSLParser#modifier.
    def enterModifier(self, ctx: BSLParser.ModifierContext):
        pass

    # Exit a parse tree produced by BSLParser#modifier.
    def exitModifier(self, ctx: BSLParser.ModifierContext):
        pass

    # Enter a parse tree produced by BSLParser#acceptor.
    def enterAcceptor(self, ctx: BSLParser.AcceptorContext):
        pass

    # Exit a parse tree produced by BSLParser#acceptor.
    def exitAcceptor(self, ctx: BSLParser.AcceptorContext):
        pass

    # Enter a parse tree produced by BSLParser#lValue.
    def enterLValue(self, ctx: BSLParser.LValueContext):
        pass

    # Exit a parse tree produced by BSLParser#lValue.
    def exitLValue(self, ctx: BSLParser.LValueContext):
        pass

    # Enter a parse tree produced by BSLParser#accessCall.
    def enterAccessCall(self, ctx: BSLParser.AccessCallContext):
        pass

    # Exit a parse tree produced by BSLParser#accessCall.
    def exitAccessCall(self, ctx: BSLParser.AccessCallContext):
        pass

    # Enter a parse tree produced by BSLParser#accessIndex.
    def enterAccessIndex(self, ctx: BSLParser.AccessIndexContext):
        pass

    # Exit a parse tree produced by BSLParser#accessIndex.
    def exitAccessIndex(self, ctx: BSLParser.AccessIndexContext):
        pass

    # Enter a parse tree produced by BSLParser#accessProperty.
    def enterAccessProperty(self, ctx: BSLParser.AccessPropertyContext):
        pass

    # Exit a parse tree produced by BSLParser#accessProperty.
    def exitAccessProperty(self, ctx: BSLParser.AccessPropertyContext):
        pass

    # Enter a parse tree produced by BSLParser#doCall.
    def enterDoCall(self, ctx: BSLParser.DoCallContext):
        pass

    # Exit a parse tree produced by BSLParser#doCall.
    def exitDoCall(self, ctx: BSLParser.DoCallContext):
        pass

    # Enter a parse tree produced by BSLParser#compoundStatement.
    def enterCompoundStatement(self, ctx: BSLParser.CompoundStatementContext):
        pass

    # Exit a parse tree produced by BSLParser#compoundStatement.
    def exitCompoundStatement(self, ctx: BSLParser.CompoundStatementContext):
        pass


del BSLParser
